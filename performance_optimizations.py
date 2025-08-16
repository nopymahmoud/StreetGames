"""
تحسينات الأداء لنظام Street Games V2
"""

# إعدادات Django لتحسين الأداء
PERFORMANCE_SETTINGS = {
    # تفعيل التخزين المؤقت
    'CACHES': {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': 'redis://127.0.0.1:6379/1',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'street_games',
            'TIMEOUT': 300,  # 5 دقائق
        }
    },
    
    # تحسين قاعدة البيانات
    'DATABASES': {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'OPTIONS': {
                'MAX_CONNS': 20,
                'conn_max_age': 600,  # 10 دقائق
            }
        }
    },
    
    # تحسين الجلسات
    'SESSION_ENGINE': 'django.contrib.sessions.backends.cached_db',
    'SESSION_CACHE_ALIAS': 'default',
    
    # تحسين الملفات الثابتة
    'STATICFILES_STORAGE': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    
    # تفعيل ضغط GZip
    'MIDDLEWARE': [
        'django.middleware.gzip.GZipMiddleware',
        # ... باقي middleware
    ],
}

# فهارس قاعدة البيانات المقترحة
DATABASE_INDEXES = """
-- فهارس للأداء المحسن

-- فهارس الإيرادات
CREATE INDEX IF NOT EXISTS idx_daily_revenue_zone_date ON accounting_dailyrevenue(zone_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_revenue_date ON accounting_dailyrevenue(date);
CREATE INDEX IF NOT EXISTS idx_daily_revenue_created_at ON accounting_dailyrevenue(created_at);

-- فهارس المصروفات
CREATE INDEX IF NOT EXISTS idx_expense_zone_date ON accounting_expense(zone_id, date);
CREATE INDEX IF NOT EXISTS idx_expense_category ON accounting_expense(category);
CREATE INDEX IF NOT EXISTS idx_expense_date ON accounting_expense(date);

-- فهارس الشراكات
CREATE INDEX IF NOT EXISTS idx_partnership_zone ON partnerships_partnership(zone_id);
CREATE INDEX IF NOT EXISTS idx_partnership_active ON partnerships_partnership(active);

-- فهارس كشوف الحسابات
CREATE INDEX IF NOT EXISTS idx_partner_account_partnership_date ON partnerships_partneraccount(partnership_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_partner_account_date ON partnerships_partneraccount(transaction_date);
CREATE INDEX IF NOT EXISTS idx_partner_account_type ON partnerships_partneraccount(transaction_type);

-- فهارس المدفوعات
CREATE INDEX IF NOT EXISTS idx_partner_payment_partnership_date ON partnerships_partnerpayment(partnership_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_partner_payment_date ON partnerships_partnerpayment(payment_date);

-- فهارس قيود اليومية
CREATE INDEX IF NOT EXISTS idx_journal_entry_date ON accounting_journalentry(entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_entry_type ON accounting_journalentry(entry_type);
CREATE INDEX IF NOT EXISTS idx_journal_entry_zone ON accounting_journalentry(zone_id);

-- فهارس معاملات الخزينة
CREATE INDEX IF NOT EXISTS idx_treasury_transaction_date ON treasury_treasurytransaction(transaction_date);
CREATE INDEX IF NOT EXISTS idx_treasury_transaction_type ON treasury_treasurytransaction(transaction_type);
"""

# استعلامات محسنة للتقارير
OPTIMIZED_QUERIES = {
    'monthly_revenue_by_zone': """
        SELECT 
            z.name as zone_name,
            z.code as zone_code,
            SUM(r.amount) as total_revenue,
            COUNT(r.id) as revenue_count
        FROM core_gamezone z
        LEFT JOIN accounting_dailyrevenue r ON z.id = r.zone_id 
            AND r.date >= %s AND r.date <= %s
        WHERE z.active = true
        GROUP BY z.id, z.name, z.code
        ORDER BY total_revenue DESC
    """,
    
    'partner_balance_summary': """
        SELECT 
            p.partner_name,
            p.percentage,
            COALESCE(SUM(pa.debit), 0) as total_debit,
            COALESCE(SUM(pa.credit), 0) as total_credit,
            COALESCE(SUM(pa.debit), 0) - COALESCE(SUM(pa.credit), 0) as balance
        FROM partnerships_partnership p
        LEFT JOIN partnerships_partneraccount pa ON p.id = pa.partnership_id
            AND pa.transaction_date >= %s AND pa.transaction_date <= %s
        WHERE p.active = true
        GROUP BY p.id, p.partner_name, p.percentage
        ORDER BY balance DESC
    """,
    
    'expense_by_category': """
        SELECT 
            category,
            COUNT(*) as expense_count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM accounting_expense
        WHERE date >= %s AND date <= %s
        GROUP BY category
        ORDER BY total_amount DESC
    """
}

# تحسينات Python/Django
def optimize_queryset_performance():
    """تحسينات QuerySet للأداء المحسن"""
    
    # استخدام select_related للعلاقات الخارجية
    optimized_queries = {
        'revenues_with_zone': """
            DailyRevenue.objects.select_related('zone', 'zone__hotel', 'created_by')
        """,
        
        'partnerships_with_zone': """
            Partnership.objects.select_related('zone', 'zone__hotel')
        """,
        
        'partner_accounts_with_partnership': """
            PartnerAccount.objects.select_related(
                'partnership', 
                'partnership__zone', 
                'created_by'
            )
        """,
        
        # استخدام prefetch_related للعلاقات المتعددة
        'zones_with_partnerships': """
            GameZone.objects.prefetch_related('partnerships')
        """,
        
        # استخدام only() لتحديد الحقول المطلوبة فقط
        'revenue_summary': """
            DailyRevenue.objects.only('zone_id', 'date', 'amount', 'currency')
        """,
        
        # استخدام defer() لتأجيل الحقول الكبيرة
        'partnerships_without_notes': """
            Partnership.objects.defer('notes')
        """
    }
    
    return optimized_queries

# تحسينات التخزين المؤقت
CACHE_STRATEGIES = {
    'dashboard_stats': {
        'key': 'dashboard_stats_{user_id}',
        'timeout': 300,  # 5 دقائق
        'description': 'إحصائيات لوحة التحكم'
    },
    
    'monthly_revenue': {
        'key': 'monthly_revenue_{zone_id}_{month}_{year}',
        'timeout': 3600,  # ساعة واحدة
        'description': 'الإيرادات الشهرية لكل منطقة'
    },
    
    'partner_balances': {
        'key': 'partner_balances_{partnership_id}',
        'timeout': 1800,  # 30 دقيقة
        'description': 'أرصدة الشركاء'
    },
    
    'chart_of_accounts': {
        'key': 'chart_of_accounts_active',
        'timeout': 7200,  # ساعتان
        'description': 'دليل الحسابات النشط'
    }
}

# إعدادات الأمان والأداء للإنتاج
PRODUCTION_SETTINGS = {
    'DEBUG': False,
    'ALLOWED_HOSTS': ['your-domain.com', 'www.your-domain.com'],
    
    # إعدادات الأمان
    'SECURE_BROWSER_XSS_FILTER': True,
    'SECURE_CONTENT_TYPE_NOSNIFF': True,
    'SECURE_HSTS_INCLUDE_SUBDOMAINS': True,
    'SECURE_HSTS_SECONDS': 31536000,
    'SECURE_SSL_REDIRECT': True,
    'SESSION_COOKIE_SECURE': True,
    'CSRF_COOKIE_SECURE': True,
    
    # تحسين الأداء
    'USE_TZ': True,
    'USE_I18N': True,
    'USE_L10N': True,
    
    # إعدادات التسجيل
    'LOGGING': {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'file': {
                'level': 'INFO',
                'class': 'logging.FileHandler',
                'filename': 'street_games.log',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }
}

# نصائح تحسين الأداء
PERFORMANCE_TIPS = """
1. استخدام Redis للتخزين المؤقت
2. تحسين استعلامات قاعدة البيانات
3. استخدام CDN للملفات الثابتة
4. ضغط الاستجابات باستخدام GZip
5. تحسين الصور والملفات الثابتة
6. استخدام connection pooling لقاعدة البيانات
7. مراقبة الأداء باستخدام أدوات مثل New Relic
8. تحسين استعلامات ORM
9. استخدام pagination للقوائم الطويلة
10. تحسين JavaScript و CSS
"""

# مراقبة الأداء
MONITORING_SETUP = """
# تثبيت أدوات المراقبة
pip install django-debug-toolbar
pip install django-extensions
pip install django-silk

# إضافة للإعدادات
INSTALLED_APPS += [
    'debug_toolbar',
    'django_extensions',
    'silk',
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'silk.middleware.SilkyMiddleware',
]

# إعدادات debug toolbar
INTERNAL_IPS = ['127.0.0.1']

# إعدادات Silk
SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True
"""

if __name__ == '__main__':
    print("تحسينات الأداء لنظام Street Games V2")
    print("=" * 50)
    print(PERFORMANCE_TIPS)
    print("\nلتطبيق التحسينات:")
    print("1. تحديث إعدادات Django")
    print("2. تطبيق فهارس قاعدة البيانات")
    print("3. تثبيت Redis للتخزين المؤقت")
    print("4. تحسين استعلامات ORM")
    print("5. مراقبة الأداء باستمرار")
