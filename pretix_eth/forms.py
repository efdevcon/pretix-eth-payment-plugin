import re

from django import forms
from django.utils.translation import gettext_lazy as _
from pretix.control.forms import ExtFileField


ADDRESS_RE = re.compile(r"^0x[a-zA-Z0-9]{40}$")
COMMENT_RE = re.compile(r"^#")


class WalletAddressTxtFile(ExtFileField):
    def __init__(self, *args, **kwargs):
        kwargs["ext_whitelist"] = (".txt",)
        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)

        if data:
            lines = data.read().decode('utf-8').splitlines()

            # Strip leading and trailing whitespace on each line; filter empty
            # lines; filter comments
            lines = [line.strip() for line in lines if line.strip()]
            lines = [line for line in lines if not COMMENT_RE.match(line)]

            if len(lines) == 0:
                raise forms.ValidationError(_("File contains no addresses"))
            for i, l in enumerate(lines, 1):
                if not ADDRESS_RE.match(l):
                    raise forms.ValidationError(
                        _("Syntax error on line {line_number}: {line_content}").format(
                            line_number=i,
                            line_content=l,
                        ),
                    )

            return "\n".join(lines)


class WalletAddressUploadForm(forms.Form):
    wallet_addresses = WalletAddressTxtFile(
        help_text=_("Upload a text file containing one \"0x\"-prefixed address per line."),
    )


class WalletAddressUploadConfirmForm(forms.Form):
    ACTION_CHOICES = (
        ('cancel', 'cancel'),
        ('confirm', 'confirm'),
    )
    action = forms.ChoiceField(choices=ACTION_CHOICES)
