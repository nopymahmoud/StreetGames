from typing import List, Tuple

def get_supported_currencies() -> List[Tuple[str, str]]:
    """ارجع قائمة العملات المسموحة بالنظام [(code, label_ar)]
    توحيداً لكل القوائم المنسدلة نجعلها ثابتة لأربع عملات: EGP, USD, EUR, GBP
    ملاحظة: سيتم إنشاء خزينة لكل عملة تلقائياً عند أول حركة نقدية بتلك العملة.
    """
    codes = ['EGP', 'USD', 'EUR', 'GBP']
    names = {
        'EGP': 'جنيه مصري',
        'USD': 'دولار أمريكي',
        'EUR': 'يورو',
        'GBP': 'جنيه استرليني',
    }
    return [(code, names.get(code, code)) for code in codes]

