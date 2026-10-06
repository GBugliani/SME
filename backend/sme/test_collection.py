from copy import deepcopy
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from .collection import collect_source, CollectionError, InfoDengueAdapter, collect_pilot
from .models import FonteEpidemiologica, RecorteGeografico, ExecucaoColeta, LoteColeta

URL = "https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2024&ey_end=2024"
ROWS = [{"SE": 202401, "casos": 12, "municipio_nome": "São Paulo", "id": 355030820240100001}]


class CollectionTests(TestCase):
    def setUp(self):
        recorte = RecorteGeografico.objects.create(tipo="municipio", nome="São Paulo", codigo="3550308", uf="SP")
        self.source = FonteEpidemiologica.objects.create(nome="InfoDengue", tipo="json", url=URL, recorte=recorte)
        self.adapter = InfoDengueAdapter()
        self.admin = get_user_model().objects.create_superuser("qa@example.org", "Strong-test-only-2026!")

    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS)
    def test_success_persists_raw_provenance_and_deduplicates(self, fetch):
        first = collect_source(self.source.pk)
        second = collect_source(self.source.pk)
        self.assertEqual(first.status, "sucesso")
        self.assertEqual(first.lote.dados_brutos, ROWS)
        self.assertEqual(first.lote.url_origem, URL)
        self.assertEqual(first.lote.territorio_codigo, "3550308")
        self.assertEqual(second.lote_id, first.lote_id)
        self.assertTrue(second.repetida)
        self.assertEqual(LoteColeta.objects.count(), 1)
        self.assertEqual(ExecucaoColeta.objects.count(), 2)
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.ultima_coleta_em)

    @patch("sme.collection.InfoDengueAdapter.fetch", side_effect=CollectionError("Fonte indisponível"))
    def test_failure_keeps_previous_success_and_next_cycle_recovers(self, fetch):
        run = collect_source(self.source.pk)
        self.assertEqual(run.status, "erro")
        self.source.refresh_from_db()
        self.assertIsNone(self.source.ultima_coleta_em)
        self.assertEqual(LoteColeta.objects.count(), 0)
        fetch.side_effect = None
        fetch.return_value = ROWS
        self.assertEqual(collect_source(self.source.pk).status, "sucesso")

    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=[])
    def test_empty_is_not_zero_cases(self, fetch):
        run = collect_source(self.source.pk)
        self.assertEqual(run.status, "vazia")
        self.assertIn("não significa zero", run.mensagem)

    def test_disabled_and_overlapping_run_do_not_fetch(self):
        self.source.ativa = False
        self.source.save()
        with patch("sme.collection.InfoDengueAdapter.fetch") as fetch:
            with self.assertRaises(CollectionError): collect_source(self.source.pk)
            fetch.assert_not_called()
        self.source.ativa = True
        self.source.save()
        ExecucaoColeta.objects.create(fonte=self.source, status="executando")
        with self.assertRaises(CollectionError): collect_source(self.source.pk)

    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS)
    def test_stale_run_is_released(self, fetch):
        old = ExecucaoColeta.objects.create(fonte=self.source, status="executando")
        ExecucaoColeta.objects.filter(pk=old.pk).update(iniciada_em=timezone.now() - timezone.timedelta(minutes=11))
        self.assertEqual(collect_source(self.source.pk).status, "sucesso")
        old.refresh_from_db()
        self.assertEqual(old.status, "erro")

    def test_rejects_foreign_hosts_credentials_redirect_target_and_mismatched_params(self):
        for url in [URL.replace("info.dengue.mat.br", "evil.example"), URL.replace("https://", "https://user:pass@"), URL.replace("geocode=3550308", "geocode=3509502"), URL + "&format=csv", URL.replace("disease=dengue", "disease=zika")]:
            with self.subTest(url=url):
                self.source.url = url
                with self.assertRaises(CollectionError): self.adapter.validate(self.source)

    def test_rejects_wrong_municipality_week_and_schema(self):
        q = self.adapter.validate(self.source)
        for change in [{"municipio_nome": "Campinas"}, {"id": 350950220240100001}, {"SE": 202553}, {"casos": -1}]:
            row = {**ROWS[0], **change}
            with self.assertRaises(CollectionError): self.adapter.validate_payload([row], self.source, q)
        with self.assertRaises(CollectionError): self.adapter.validate_payload(ROWS * 2, self.source, q)
        with self.assertRaises(CollectionError): self.adapter.validate_payload({"error": "not available"}, self.source, q)

    @patch("sme.collection.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))])
    def test_private_dns_is_blocked_before_connection(self, dns):
        with patch("sme.collection.socket.create_connection") as connect:
            with self.assertRaises(CollectionError): self.adapter.fetch(self.source)
            connect.assert_not_called()

    @patch("sme.collection.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))])
    @patch("sme.collection.ssl.create_default_context")
    @patch("sme.collection.socket.create_connection")
    @patch("sme.collection.http.client.HTTPSConnection")
    def test_redirect_is_rejected_without_second_request(self, cls, sock, context, dns):
        conn = cls.return_value
        conn.getresponse.return_value.status = 302
        with self.assertRaises(CollectionError): self.adapter.fetch(self.source)
        self.assertEqual(conn.request.call_count, 1)

    @patch("sme.collection.InfoDengueAdapter.fetch")
    def test_configuration_change_during_fetch_discards_payload(self, fetch):
        def change(source):
            FonteEpidemiologica.objects.filter(pk=source.pk).update(ativa=False)
            return ROWS
        fetch.side_effect = change
        self.assertEqual(collect_source(self.source.pk).status, "erro")
        self.assertEqual(LoteColeta.objects.count(), 0)

    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS)
    def test_manual_endpoint_requires_admin_and_exposes_history(self, fetch):
        url = f"/api/fontes/{self.source.pk}/coletas/"
        self.assertEqual(self.client.post(url).status_code, 401)
        user = get_user_model().objects.create_user("user@example.org", "Strong-test-only-2026!")
        self.client.force_login(user)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url).status_code, 200)
        data = self.client.get(url).json()["execucoes"]
        self.assertEqual(data[0]["quantidade_registros"], 1)
        self.assertNotIn("dados_brutos", data[0])

    @override_settings(COLLECTION_TOKEN="test-only-token")
    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS)
    def test_scheduler_endpoint_requires_dedicated_token(self, fetch):
        self.assertEqual(self.client.post("/api/internal/coleta/").status_code, 403)
        self.assertEqual(self.client.post("/api/internal/coleta/", HTTP_X_COLETA_TOKEN="wrong").status_code, 403)
        response = self.client.post("/api/internal/coleta/", {}, content_type="application/json", HTTP_X_COLETA_TOKEN="test-only-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["execucoes"][0]["origem"], "airflow")

    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS)
    def test_failure_preserves_last_successful_timestamp(self, fetch):
        collect_source(self.source.pk)
        self.source.refresh_from_db()
        stamp = self.source.ultima_coleta_em
        fetch.side_effect = CollectionError("Tempo esgotado")
        self.assertEqual(collect_source(self.source.pk).status, "erro")
        self.source.refresh_from_db()
        self.assertEqual(self.source.ultima_coleta_em, stamp)

    @patch("sme.collection.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))])
    @patch("sme.collection.ssl.create_default_context")
    @patch("sme.collection.socket.create_connection")
    @patch("sme.collection.http.client.HTTPSConnection")
    def test_invalid_and_oversized_remote_responses_are_rejected(self, cls, sock, context, dns):
        conn = cls.return_value
        response = conn.getresponse.return_value
        response.status = 200
        for body in [b"<html>indisponivel</html>", b"x" * (5 * 1024 * 1024 + 1)]:
            response.read.return_value = body
            with self.assertRaises(CollectionError): self.adapter.fetch(self.source)

    @patch("sme.collection.socket.getaddrinfo", side_effect=TimeoutError())
    def test_timeout_becomes_recorded_failure(self, dns):
        run = collect_source(self.source.pk)
        self.assertEqual(run.status, "erro")
        self.assertIsNotNone(run.finalizada_em)


    def test_other_sp_municipality_and_unknown_or_mismatched_territory(self):
        self.source.recorte.codigo = "3510500"
        self.source.recorte.nome = "Caraguatatuba"
        self.source.url = URL.replace("3550308", "3510500")
        q = self.adapter.validate(self.source)
        rows = [{**ROWS[0], "municipio_nome": "Caraguatatuba", "id": 351050020240100001}]
        self.adapter.validate_payload(rows, self.source, q)
        with self.assertRaises(CollectionError):
            self.adapter.validate_payload(ROWS, self.source, q)
        for code, name, uf in [("3599999", "Inexistente", "SP"), ("3510500", "Campinas", "SP"), ("3510500", "Caraguatatuba", "RJ")]:
            self.source.recorte.codigo, self.source.recorte.nome, self.source.recorte.uf = code, name, uf
            self.source.url = URL.replace("3550308", code)
            with self.assertRaises(CollectionError): self.adapter.validate(self.source)

    @patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS)
    def test_scheduler_covers_more_than_five_sources_and_skips_disabled(self, fetch):
        for i in range(6):
            FonteEpidemiologica.objects.create(nome=f"Fonte {i}", tipo="json", url=URL + ":" + str(i), recorte=self.source.recorte)
        # URLs distintas mas válidas: parâmetros em ordem diferente.
        for i, source in enumerate(FonteEpidemiologica.objects.exclude(pk=self.source.pk)):
            source.url = URL.replace("ew_start=1", "ew_start=" + "0" * (i + 1) + "1")
            source.save()
        self.assertEqual(len(collect_pilot()), 7)
        self.source.ativa = False
        self.source.save()
        self.assertEqual(len(collect_pilot()), 6)

    @override_settings(COLLECTION_TOKEN="test-token")
    def test_scheduler_lists_and_collects_individual_sources(self):
        headers = {"HTTP_X_COLETA_TOKEN": "test-token"}
        response = self.client.post("/api/internal/coleta/", {"action": "list"}, content_type="application/json", **headers)
        self.assertEqual(response.json()["fontes"], [self.source.pk])
        with patch("sme.collection.InfoDengueAdapter.fetch", return_value=ROWS):
            response = self.client.post("/api/internal/coleta/", {"fonte_id": self.source.pk}, content_type="application/json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["execucoes"][0]["origem"], "airflow")
        self.source.ativa = False
        self.source.save()
        response = self.client.post("/api/internal/coleta/", {"fonte_id": self.source.pk}, content_type="application/json", **headers)
        self.assertEqual(response.status_code, 400)
