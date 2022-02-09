from django.contrib import admin
from django.contrib import messages
from .models import *

# Register your models here.
admin.site.register(PlayerBase)
admin.site.register(EmailConfirmationRequest)
admin.site.register(PasswordRecoveryRequest)
admin.site.register(Manager)
admin.site.register(BlogPost)
admin.site.register(Settings)
admin.site.register(Transaction)
admin.site.register(MarketOffer)
admin.site.register(Bundle)
admin.site.register(TokenInfo)
admin.site.register(SuspiciousTransaction)
admin.site.register(Blacklist)
admin.site.register(TesterInvitation)
admin.site.register(Setup)
admin.site.register(OffchainCrownCredit)

class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = [field.name for field in TransactionHistory._meta.get_fields()]

class WithdrawTaxAdmin(admin.ModelAdmin):
    list_display = [field.name for field in WithdrawTax._meta.get_fields()]

    def save_model(self, request, obj, form, change):
        token_type = form.cleaned_data['token_type']
        res = list(WithdrawTax.objects.filter(token_type=token_type).values_list())
        if len(res) == 0:
            super().save_model(request, obj, form, change)
        else:
            messages.add_message(request, messages.ERROR, 'Tax is already recorded for this token')

    def message_user(self, *args):  # overridden method
        pass

    class Meta:
        model = WithdrawTax

admin.site.register(WithdrawTax, WithdrawTaxAdmin)
admin.site.register(TransactionHistory, TransactionHistoryAdmin)