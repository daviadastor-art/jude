-- توحيد عملة iChancy والبوت على الليرة السورية الجديدة بنسبة 1=1.
-- يُنفّذ مرة واحدة فقط بعد الترحيل السابق 20260921_syp_new.
-- لا يُعاد تقسيم bot_balance أو البونصات لأنها أصبحت بالفعل بالليرة الجديدة.
BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(120) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '20261101_unify_syp_ichancy') THEN
        -- game_balance كان الحقل الوحيد الباقي بوحدة iChancy القديمة.
        UPDATE users
        SET game_balance = FLOOR(COALESCE(game_balance, 0) / 100);

        -- لقطات أرصدة اللعبة في عمولات الإحالات الأسبوعية.
        UPDATE affiliate_weekly_commissions
        SET ending_game_balance = FLOOR(COALESCE(ending_game_balance, 0) / 100);

        -- السجلات التاريخية: amount و converted_amount_syp سبق توحيدهما،
        -- أما original_amount لعمليات اللعبة فكان يحتفظ بالقيمة القديمة.
        UPDATE transactions
        SET original_amount = FLOOR(COALESCE(original_amount, 0) / 100)
        WHERE type = 'withdraw_from_game'
          AND LOWER(COALESCE(original_currency, '')) IN ('syp', 'nsp', 'syp_old');

        UPDATE bot_settings
        SET exchange_rate = 1,
            syp_version = 'new';

        INSERT INTO schema_migrations(version) VALUES ('20261101_unify_syp_ichancy');
    END IF;
END $$;

COMMIT;
