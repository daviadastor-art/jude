"""Database backup generation and Telegram delivery helpers."""
from __future__ import annotations

import asyncio
import gzip
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from psycopg2 import connect
from psycopg2.extensions import adapt

from config import settings

logger = logging.getLogger(__name__)
BACKUP_CHANNEL_ID = str(getattr(settings, "BACKUP_CHANNEL_ID", "-1004487457598"))
BACKUP_LOCK = asyncio.Lock()


def _backup_name() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"jude_database_backup_{stamp}.sql.gz"


def _portable_sql_dump(database_url: str, sql_path: Path) -> None:
    """Fallback dump using psycopg2 when the PostgreSQL CLI is unavailable."""
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor, sql_path.open("w", encoding="utf-8") as output:
            output.write("-- Jude portable database backup\nBEGIN;\n")
            cursor.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """)
            tables = cursor.fetchall()
            for schema, table in tables:
                qualified = f'"{schema.replace(chr(34), chr(34) * 2)}"."{table.replace(chr(34), chr(34) * 2)}"'
                cursor.execute("""
                    SELECT a.attname,
                           pg_catalog.format_type(a.atttypid, a.atttypmod),
                           a.attnotnull,
                           pg_catalog.pg_get_expr(d.adbin, d.adrelid)
                    FROM pg_catalog.pg_attribute a
                    JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                    WHERE n.nspname = %s AND c.relname = %s
                      AND a.attnum > 0 AND NOT a.attisdropped
                    ORDER BY a.attnum
                """, (schema, table))
                columns = cursor.fetchall()
                definitions = []
                names = []
                for name, type_name, not_null, default in columns:
                    quoted = '"' + name.replace('"', '""') + '"'
                    names.append(quoted)
                    definition = f"{quoted} {type_name}"
                    if default:
                        definition += f" DEFAULT {default}"
                    if not_null:
                        definition += " NOT NULL"
                    definitions.append(definition)
                output.write(f"DROP TABLE IF EXISTS {qualified} CASCADE;\nCREATE TABLE {qualified} (\n  " + ",\n  ".join(definitions) + "\n);\n")
                cursor.execute(f"SELECT * FROM {qualified}")
                for row in cursor.fetchall():
                    values = ', '.join('NULL' if value is None else adapt(value).getquoted().decode('utf-8') for value in row)
                    output.write(f"INSERT INTO {qualified} ({', '.join(names)}) VALUES ({values});\n")
            output.write("COMMIT;\n")
    finally:
        connection.close()


def create_database_backup() -> tuple[str, int]:
    """Create a compressed plain SQL dump containing every database object/data row."""
    database_url = getattr(settings, "DATABASE_URL", None) or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL غير مضبوط")
    pg_dump = os.getenv("PG_DUMP_PATH") or shutil.which("pg_dump")
    temp_dir = Path(tempfile.mkdtemp(prefix="jude_backup_"))
    sql_path = temp_dir / "database.sql"
    archive_path = temp_dir / _backup_name()
    try:
        if pg_dump:
            command = [
                pg_dump, "--dbname", database_url, "--format=plain",
                "--no-owner", "--no-privileges", "--encoding=UTF8",
                "--file", str(sql_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=900)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "pg_dump failed").strip()[-1500:]
                raise RuntimeError(f"فشل pg_dump: {detail}")
        else:
            logger.warning("pg_dump غير موجود؛ سيتم استخدام النسخة المحمولة عبر psycopg2")
            _portable_sql_dump(database_url, sql_path)
        with sql_path.open("rb") as source, gzip.open(archive_path, "wb", compresslevel=6) as target:
            shutil.copyfileobj(source, target)
        size = archive_path.stat().st_size
        if size <= 0:
            raise RuntimeError("ملف النسخ الناتج فارغ")
        return str(archive_path), size
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def cleanup_backup_file(path: str) -> None:
    path_obj = Path(path)
    shutil.rmtree(path_obj.parent, ignore_errors=True)


def _progress_bar(percent: int, width: int = 20) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round(width * percent / 100)
    return f"[{'█' * filled}{'░' * (width - filled)}] {percent}%"


def progress_text(percent: int, stage: str) -> str:
    return (
        "🗄️ <b>النسخ الاحتياطي لقاعدة البيانات</b>\n\n"
        f"{_progress_bar(percent)}\n"
        f"🔄 الحالة: {stage}\n"
        "📦 سيتم تضمين جميع الجداول والبيانات داخل الملف."
    )


async def run_backup_and_send(bot: Bot, progress_message=None, trigger: str = "يدوي") -> bool:
    """Generate a full dump, send it to the configured channel, and clean temp files."""
    if BACKUP_LOCK.locked():
        if progress_message:
            await progress_message.edit_text("⏳ يوجد نسخ احتياطي قيد التنفيذ حالياً. انتظر حتى يكتمل.")
        return False
    async with BACKUP_LOCK:
        path = None
        try:
            if progress_message:
                await progress_message.edit_text(progress_text(10, "تجهيز اتصال قاعدة البيانات..."), parse_mode="HTML")
            await asyncio.sleep(0)
            if progress_message:
                await progress_message.edit_text(progress_text(25, "جلب بنية الجداول والبيانات..."), parse_mode="HTML")
            path, size = await asyncio.to_thread(create_database_backup)
            if progress_message:
                await progress_message.edit_text(progress_text(80, "ضغط الملف وتجهيزه للإرسال..."), parse_mode="HTML")
            size_mb = size / (1024 * 1024)
            caption = (
                "🗄️ <b>نسخة احتياطية كاملة لقاعدة البيانات</b>\n\n"
                f"📅 الوقت: <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</code>\n"
                f"📦 الحجم المضغوط: <code>{size_mb:.2f} MB</code>\n"
                f"🔁 المصدر: <code>{trigger}</code>\n"
                "✅ جميع الجداول والبيانات مشمولة."
            )
            if progress_message:
                await progress_message.edit_text(progress_text(90, "إرسال الملف إلى قناة النسخ..."), parse_mode="HTML")
            await bot.send_document(
                chat_id=BACKUP_CHANNEL_ID,
                document=FSInputFile(path, filename=Path(path).name),
                caption=caption,
                parse_mode="HTML",
            )
            if progress_message:
                await progress_message.edit_text(progress_text(100, "اكتمل النسخ والإرسال بنجاح ✅"), parse_mode="HTML")
            return True
        except Exception as exc:
            logger.error("Database backup failed", exc_info=True)
            if progress_message:
                try:
                    await progress_message.edit_text(
                        "⛔ <b>فشل النسخ الاحتياطي</b>\n\n"
                        f"<code>{str(exc)[:1200]}</code>\n\n"
                        "تحقق من صلاحية قاعدة البيانات ووجود pg_dump وصلاحية البوت في القناة.",
                        parse_mode="HTML",
                    )
                except Exception:
                    logger.exception("Failed to report backup error")
            return False
        finally:
            if path:
                cleanup_backup_file(path)
