import ipaddress
from urllib.parse import urlsplit
from django import forms

UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


class FonteForm(forms.Form):
    nome = forms.CharField(max_length=150)
    tipo = forms.ChoiceField(choices=[("csv", "CSV"), ("json", "JSON/API")])
    url = forms.URLField(max_length=2000, assume_scheme="https")
    recorte_tipo = forms.ChoiceField(choices=[("municipio", "Município"), ("regiao", "Região")])
    recorte_nome = forms.CharField(max_length=150)
    recorte_codigo = forms.CharField(max_length=50)
    recorte_uf = forms.CharField(max_length=2, required=False)
    ativa = forms.BooleanField(required=False)

    def clean_url(self):
        url = self.cleaned_data["url"]
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
            raise forms.ValidationError("Use uma URL HTTPS pública, sem credenciais ou fragmentos.")
        try:
            port = parsed.port
        except ValueError:
            raise forms.ValidationError("A porta informada é inválida.")
        if port not in (None, 443):
            raise forms.ValidationError("Use a porta HTTPS padrão (443).")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
            raise forms.ValidationError("Informe o endereço de uma fonte pública.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not address.is_global:
                raise forms.ValidationError("Endereços privados não são permitidos.")
        return url

    def clean(self):
        data = super().clean()
        uf = data.get("recorte_uf", "").upper()
        data["recorte_uf"] = uf
        if uf and uf not in UFS:
            self.add_error("recorte_uf", "Informe uma UF brasileira válida.")
        if data.get("recorte_tipo") == "municipio":
            code = data.get("recorte_codigo", "")
            if len(code) != 7 or not code.isascii() or not code.isdigit():
                self.add_error("recorte_codigo", "O código IBGE deve conter 7 dígitos.")
            if not uf:
                self.add_error("recorte_uf", "Informe a UF do município.")
        return data
