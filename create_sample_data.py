#!/usr/bin/env python
import os
import django
from django.conf import settings
from decimal import Decimal
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'street_games.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Hotel, GameZone, GameType, Warehouse, UserProfile
from partnerships.models import Partnership, PartnerAccount, PartnerPayment
from accounting.models import ChartOfAccounts, DailyRevenue
from accounting.expense_models import Expense
from treasury.models import Treasury, BankAccount
from purchases.models import Supplier, PurchaseBill, PurchaseBillLine, PurchaseReturn, PurchaseReturnLine, post_purchase_bill, post_purchase_return
from purchases.payments import supplier_payment


def create_sample_data():
    print("إنشاء البيانات التجريبية...")
    
    # إنشاء المستخدمين
    admin_user = User.objects.get(username='admin')
    
    # إنشاء مستخدم محاسب
    accountant_user, created = User.objects.get_or_create(
        username='accountant',
        defaults={
            'first_name': 'أحمد',
            'last_name': 'المحاسب',
            'email': 'accountant@streetgames.com',
            'is_staff': True
        }
    )
    if created:
        accountant_user.set_password('accountant123')
        accountant_user.save()
        accountant_user.userprofile.role = 'accountant'
        accountant_user.userprofile.save()
    
    # إنشاء مستخدم مدير منطقة
    zone_manager, created = User.objects.get_or_create(
        username='zone_manager',
        defaults={
            'first_name': 'محمد',
            'last_name': 'مدير المنطقة',
            'email': 'manager@streetgames.com',
            'is_staff': True
        }
    )
    if created:
        zone_manager.set_password('manager123')
        zone_manager.save()
        zone_manager.userprofile.role = 'zone_manager'
        zone_manager.userprofile.save()
    
    # إنشاء الفنادق
    hotel1, created = Hotel.objects.get_or_create(
        name='فندق الشاطئ الذهبي',
        defaults={
            'location': 'الغردقة - البحر الأحمر',
            'manager': admin_user,
            'active': True
        }
    )
    
    hotel2, created = Hotel.objects.get_or_create(
        name='منتجع النخيل',
        defaults={
            'location': 'شرم الشيخ - جنوب سيناء',
            'manager': admin_user,
            'active': True
        }
    )
    
    # إنشاء أنواع الألعاب
    game_types = [
        ('ألعاب إلكترونية', 'ELEC001', 'electronic'),
        ('ألعاب هوائية', 'INFL001', 'inflatable'),
        ('مركبات', 'VEHI001', 'vehicles'),
        ('ألعاب أركيد', 'ARCA001', 'arcade'),
        ('واقع افتراضي', 'VR001', 'vr'),
    ]
    
    for name, code, category in game_types:
        GameType.objects.get_or_create(
            name=name,
            defaults={'code': code, 'category': category, 'active': True}
        )
    
    # إنشاء مناطق الألعاب
    zones_data = [
        ('منطقة الشاطئ', 'BEACH01', hotel1, 15000, '2024-01-01'),
        ('منطقة الأطفال', 'KIDS01', hotel1, 12000, '2024-01-01'),
        ('منطقة VR', 'VR01', hotel1, 20000, '2024-02-01'),
        ('منطقة الأركيد', 'ARCADE01', hotel2, 18000, '2024-01-01'),
        ('منطقة المغامرات', 'ADVENT01', hotel2, 25000, '2024-03-01'),
    ]
    
    zones = []
    for name, code, hotel, rent, opening_date in zones_data:
        zone, created = GameZone.objects.get_or_create(
            name=name,
            code=code,
            defaults={
                'hotel': hotel,
                'monthly_rent': Decimal(str(rent)),
                'currency': 'EGP',
                'manager': zone_manager,
                'active': True,
                'opening_date': datetime.strptime(opening_date, '%Y-%m-%d').date(),
                'revenue_account': '4100',
                'expense_account': '5100'
            }
        )
        zones.append(zone)
    
    # إضافة صلاحيات للمستخدمين
    zone_manager.userprofile.allowed_zones.set(zones[:3])  # أول 3 مناطق
    accountant_user.userprofile.can_access_all_zones = True
    accountant_user.userprofile.save()
    
    # إنشاء المخازن
    warehouses_data = [
        ('المخزن الرئيسي', 'MAIN01', 'القاهرة - مدينة نصر', 'main'),
        ('مخزن قطع الغيار', 'SPARE01', 'الغردقة', 'spare_parts'),
        ('مخزن الصيانة', 'MAINT01', 'شرم الشيخ', 'maintenance'),
    ]
    
    for name, code, location, warehouse_type in warehouses_data:
        Warehouse.objects.get_or_create(
            name=name,
            code=code,
            defaults={
                'location': location,
                'warehouse_type': warehouse_type,
                'manager': admin_user,
                'active': True
            }
        )
    
    # إنشاء دليل الحسابات الأساسي
    accounts_data = [
        ('1000', 'الأصول', 'asset', None, 'debit', 0),
        ('1100', 'الأصول المتداولة', 'asset', '1000', 'debit', 0),
        ('1110', 'الخزينة', 'asset', '1100', 'debit', 50000),
        ('1120', 'البنوك', 'asset', '1100', 'debit', 100000),
        ('1200', 'الأصول الثابتة', 'asset', '1000', 'debit', 0),
        ('1210', 'المعدات والألعاب', 'asset', '1200', 'debit', 500000),
        
        ('2000', 'الخصوم', 'liability', None, 'credit', 0),
        ('2100', 'الخصوم المتداولة', 'liability', '2000', 'credit', 0),
        ('2110', 'الموردون', 'liability', '2100', 'credit', 25000),
        
        ('3000', 'حقوق الملكية', 'equity', None, 'credit', 0),
        ('3100', 'رأس المال', 'equity', '3000', 'credit', 500000),
        
        ('4000', 'الإيرادات', 'revenue', None, 'credit', 0),
        ('4100', 'إيرادات الألعاب', 'revenue', '4000', 'credit', 0),
        
        ('5000', 'المصروفات', 'expense', None, 'debit', 0),
        ('5100', 'مصروفات التشغيل', 'expense', '5000', 'debit', 0),
        ('5110', 'الإيجارات', 'expense', '5100', 'debit', 0),
        ('5120', 'الرواتب', 'expense', '5100', 'debit', 0),
        ('5130', 'الصيانة', 'expense', '5100', 'debit', 0),
    ]
    
    for code, name, acc_type, parent_code, balance_type, opening_balance in accounts_data:
        parent = None
        if parent_code:
            parent = ChartOfAccounts.objects.filter(account_code=parent_code).first()
        
        ChartOfAccounts.objects.get_or_create(
            account_code=code,
            defaults={
                'account_name': name,
                'account_type': acc_type,
                'parent_account': parent,
                'balance_type': balance_type,
                'opening_balance': Decimal(str(opening_balance)),
                'current_balance': Decimal(str(opening_balance)),
                'currency': 'EGP',
                'active': True
            }
        )
    
    # إنشاء الخزينة والبنوك
    Treasury.objects.get_or_create(
        currency='EGP',
        defaults={'balance': Decimal('50000'), 'chart_account_code': '1110'}
    )
    
    BankAccount.objects.get_or_create(
        bank_name='البنك الأهلي المصري',
        account_number='123456789',
        defaults={
            'account_name': 'حساب شركة ألعاب الشارع',
            'currency': 'EGP',
            'opening_balance': Decimal('100000'),
            'current_balance': Decimal('100000'),
            'chart_account_code': '1120',
            'active': True
        }
    )
    
    # إنشاء الشراكات
    partnerships_data = [
        (zones[0], 'أحمد محمد علي', 'individual', '12345678901234', '', 40, 150000),
        (zones[0], 'شركة الترفيه المتقدم', 'company', '', '12345', 35, 200000),
        (zones[0], 'محمد أحمد حسن', 'individual', '98765432109876', '', 25, 100000),
        (zones[1], 'سارة محمود', 'individual', '11111111111111', '', 50, 120000),
        (zones[1], 'شركة الألعاب الذكية', 'company', '', '67890', 50, 180000),
        (zones[2], 'مستثمر VR', 'investor', '', '', 60, 300000),
        (zones[2], 'شريك تقني', 'individual', '22222222222222', '', 40, 200000),
    ]
    
    created_partnerships = []
    for zone, name, partner_type, national_id, commercial_register, percentage, investment in partnerships_data:
        partnership, created = Partnership.objects.get_or_create(
            zone=zone,
            partner_name=name,
            defaults={
                'partner_type': partner_type,
                'national_id': national_id,
                'commercial_register': commercial_register,
                'percentage': Decimal(str(percentage)),
                'investment_amount': Decimal(str(investment)),
                'currency': 'EGP',
                'start_date': datetime(2024, 1, 1).date(),
                'share_expenses': True,
                'active': True
            }
        )
        created_partnerships.append(partnership)
    
    # إنشاء إيرادات تجريبية للشهرين الماضيين
    base_date = datetime.now().date().replace(day=1) - timedelta(days=60)
    
    for i in range(60):  # 60 يوم من البيانات
        current_date = base_date + timedelta(days=i)
        
        for zone in zones[:3]:  # أول 3 مناطق فقط
            # إيراد عشوائي بين 2000-8000 جنيه
            import random
            amount = random.randint(2000, 8000)
            
            revenue, created = DailyRevenue.objects.get_or_create(
                zone=zone,
                date=current_date,
                defaults={
                    'amount': Decimal(str(amount)),
                    'currency': 'EGP',
                    'payment_method': random.choice(['cash', 'card', 'mixed']),
                    'created_by': admin_user,
                    'partner_shares_calculated': True
                }
            )
    
    # إنشاء مصروفات تجريبية
    expense_categories = ['rent', 'maintenance', 'salary', 'utilities', 'supplies']
    
    for i in range(30):  # 30 مصروف
        current_date = base_date + timedelta(days=i*2)
        
        for zone in zones[:3]:
            category = random.choice(expense_categories)
            amount = random.randint(500, 3000)
            
            expense, created = Expense.objects.get_or_create(
                zone=zone,
                date=current_date,
                category=category,
                defaults={
                    'description': f'مصروف {category} - {zone.name}',
                    'amount': Decimal(str(amount)),
                    'currency': 'EGP',
                    'charge_partners': True,
                    'created_by': admin_user,
                    'partner_shares_calculated': True
                }
            )
    
    print("تم إنشاء البيانات التجريبية بنجاح!")
    print(f"تم إنشاء {Hotel.objects.count()} فندق")
    print(f"تم إنشاء {GameZone.objects.count()} منطقة ألعاب")
    print(f"تم إنشاء {Partnership.objects.count()} شراكة")
    print(f"تم إنشاء {DailyRevenue.objects.count()} إيراد")
    print(f"تم إنشاء {Expense.objects.count()} مصروف")
    print(f"تم إنشاء {ChartOfAccounts.objects.count()} حساب محاسبي")


if __name__ == '__main__':
    create_sample_data()
