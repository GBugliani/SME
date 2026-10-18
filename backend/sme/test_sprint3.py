import csv
import io
import json
from datetime import datetime, time, timezone
from unittest.mock import patch
from django.test import TestCase, Client
from .models import (Usuario, PerfilAcesso, RegistroAuditoria, RecorteGeografico,
                     FonteEpidemiologica, LoteColeta)
from .processing import process_lote, week_start

PASSWORD = 'S3-QA-long-password-2026!'


class AccessAdministrationTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser('admin@example.org', PASSWORD)
        self.reader = Usuario.objects.create_user('reader@example.org', PASSWORD)
        self.profile = PerfilAcesso.objects.get(codigo='usuario')
        self.admin_profile = PerfilAcesso.objects.get(codigo='administrador')
        self.client.force_login(self.admin)

    def body(self, **overrides):
        return {'nome': 'Pessoa de teste', 'email': 'new@example.org', 'ativo': True,
                'perfil_id': self.profile.pk, 'password': PASSWORD, 'password_confirmation': PASSWORD, **overrides}

    def post_user(self, **overrides):
        return self.client.post('/api/administracao/usuarios/', self.body(**overrides), content_type='application/json')

    def edit(self, user, **overrides):
        body = {'nome': user.first_name or 'Pessoa', 'email': user.email, 'ativo': user.is_active,
                'perfil_id': self.admin_profile.pk if user.is_staff else self.profile.pk, **overrides}
        return self.client.put(f'/api/administracao/usuarios/{user.pk}/', body, content_type='application/json')

    def test_create_hashes_password_and_audits_without_credentials(self):
        response = self.post_user(email='NEW@EXAMPLE.ORG')
        self.assertEqual(response.status_code, 201, response.content)
        user = Usuario.objects.get(email='new@example.org')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertFalse(user.is_staff or user.is_superuser)
        entry = RegistroAuditoria.objects.get(acao='usuario_criado')
        self.assertEqual(entry.usuario, self.admin)
        self.assertNotIn('password', json.dumps(entry.detalhes))
        self.assertNotIn(PASSWORD, response.content.decode())

    def test_create_admin_does_not_grant_superuser(self):
        self.assertEqual(self.post_user(perfil_id=self.admin_profile.pk).status_code, 201)
        user = Usuario.objects.get(email='new@example.org')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_invalid_registration_is_atomic(self):
        for fields in [{'password': 'short', 'password_confirmation': 'short'}, {'email': 'invalid'},
                       {'ativo': 'true'}, {'perfil_id': True}, {'is_superuser': True},
                       {'password_confirmation': 'wrong'}, {'nome': ' '}, {'perfil_id': 99999}]:
            with self.subTest(fields=fields):
                self.assertIn(self.post_user(**fields).status_code, (400, 404))
        self.assertEqual(Usuario.objects.count(), 2)
        self.assertFalse(RegistroAuditoria.objects.exists())

    def test_duplicate_email_is_case_insensitive(self):
        self.assertIn(self.post_user(email='READER@EXAMPLE.ORG').status_code, (400, 409))

    def test_user_update_keeps_password_and_audits_changes(self):
        old = self.reader.password
        response = self.edit(self.reader, nome='Novo nome', email='updated@example.org')
        self.assertEqual(response.status_code, 200, response.content)
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.password, old)
        record = RegistroAuditoria.objects.get(acao='usuario_editado')
        self.assertEqual(record.detalhes['antes']['email'], 'reader@example.org')
        self.assertEqual(record.detalhes['depois']['email'], 'updated@example.org')

    def test_cannot_disable_or_demote_self(self):
        for change in [{'ativo': False}, {'perfil_id': self.profile.pk}]:
            self.assertEqual(self.edit(self.admin, **change).status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active and self.admin.is_staff)

    def test_staff_cannot_edit_superuser_or_reset_password(self):
        other = Usuario.objects.create_user('staff@example.org', PASSWORD, is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.edit(self.admin, nome='Changed').status_code, 403)
        self.assertEqual(self.edit(self.reader, password='attempt').status_code, 400)

    def test_disabled_account_loses_existing_session(self):
        other = Client(); other.force_login(self.reader)
        self.assertEqual(other.get('/api/auth/me/').status_code, 200)
        self.assertEqual(self.edit(self.reader, ativo=False).status_code, 200)
        self.assertEqual(other.get('/api/fontes/').status_code, 401)
        self.assertEqual(self.edit(self.reader, ativo=True).status_code, 200)
        self.assertEqual(other.get('/api/auth/me/').status_code, 401)

    def test_reader_and_anonymous_cannot_manage_or_read_audit(self):
        urls = ['/api/administracao/usuarios/', '/api/administracao/perfis/', '/api/administracao/auditoria/']
        self.client.force_login(self.reader)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            if 'auditoria' not in url:
                self.assertEqual(self.client.post(url, {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.edit(self.reader, perfil_id=self.admin_profile.pk).status_code, 403)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_csrf_required_for_admin_mutations(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.admin)
        self.assertEqual(client.post('/api/administracao/usuarios/', self.body(), content_type='application/json').status_code, 403)
        self.assertEqual(client.put(f'/api/administracao/perfis/{self.profile.pk}/', {}, content_type='application/json').status_code, 403)

    def test_custom_permissions_are_enforced_and_revoked_in_existing_session(self):
        response = self.client.post('/api/administracao/perfis/', {'nome': 'Operador', 'permissoes': ['gerenciar_fontes']}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        pk = response.json()['perfil']['id']
        self.assertEqual(self.edit(self.reader, perfil_id=pk).status_code, 200)
        other = Client(); other.force_login(self.reader)
        self.assertEqual(other.get('/api/fontes/catalogo/').status_code, 200)
        self.assertEqual(other.post('/api/fontes/', {}, content_type='application/json').status_code, 400)
        self.assertEqual(other.post('/api/fontes/1/coletas/', {}, content_type='application/json').status_code, 403)
        self.assertEqual(other.get('/api/indicadores/exportar/').status_code, 403)
        self.assertEqual(other.get('/api/administracao/usuarios/').status_code, 403)
        self.client.put(f'/api/administracao/perfis/{pk}/', {'nome':'Operador','permissoes':[]}, content_type='application/json')
        self.assertEqual(other.get('/api/fontes/catalogo/').status_code, 403)
        self.assertEqual(other.get('/api/fontes/').status_code, 200)

    def test_collector_cannot_edit_sources(self):
        p = PerfilAcesso.objects.create(nome='Coletor', permissoes=['coletar_dados'])
        self.edit(self.reader, perfil_id=p.pk)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get('/api/fontes/catalogo/').status_code, 403)
        self.assertEqual(self.client.post('/api/fontes/', {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post('/api/fontes/999/coletas/', {}, content_type='application/json').status_code, 404)

    def test_profile_whitelist_standard_profiles_and_unique_names(self):
        url = '/api/administracao/perfis/'
        for body in [{'nome':'Admin2','permissoes':['administrador']}, {'nome':'Bad','permissoes':[{}]},
                     {'nome':'Admin2','permissoes':[],'codigo':'administrador'}]:
            self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 400)
        response = self.client.post(url, {'nome':'Leitor restrito','permissoes':[]}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn(self.client.post(url, {'nome':'LEITOR RESTRITO','permissoes':[]}, content_type='application/json').status_code, (400,409))
        self.assertEqual(self.client.put(f'{url}{self.admin_profile.pk}/', {'nome':'Admin','permissoes':[]}, content_type='application/json').status_code, 400)

    def test_user_search_pagination_and_audit_are_admin_only(self):
        for i in range(23):
            Usuario.objects.create_user(f'test{i}@example.org', PASSWORD, first_name='Teste')
        page = self.client.get('/api/administracao/usuarios/', {'q':'Teste','page':2}).json()
        self.assertEqual((page['count'], len(page['usuarios'])), (23,3))
        self.assertEqual(self.client.get('/api/administracao/usuarios/', {'q':"' OR 1=1 --"}).json()['count'], 0)
        self.post_user()
        self.assertEqual(self.client.get('/api/administracao/auditoria/').json()['registros'][0]['acao'], 'usuario_criado')

    def reset_password(self, target=None, client=None, **changes):
        return (client or self.client).post(f'/api/administracao/usuarios/{(target or self.reader).pk}/senha/', {
            'password':'New-password-2026-strong!', 'password_confirmation':'New-password-2026-strong!',
            'admin_password': PASSWORD, **changes}, content_type='application/json')

    def test_admin_reset_invalidates_sessions_and_audits_without_secrets(self):
        other = Client(); other.force_login(self.reader)
        response = self.reset_password()
        self.assertEqual(response.status_code, 200, response.content)
        self.reader.refresh_from_db()
        self.assertTrue(self.reader.check_password('New-password-2026-strong!'))
        self.assertFalse(self.reader.check_password(PASSWORD))
        self.assertEqual(other.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        entry = RegistroAuditoria.objects.get(acao='senha_redefinida')
        self.assertEqual(entry.usuario, self.admin)
        self.assertEqual(entry.entidade_id, self.reader.pk)
        self.assertEqual(entry.detalhes, {})

    def test_reset_requires_admin_csrf_reauthentication_and_valid_password(self):
        for changes in [{'admin_password':'wrong'}, {'password':'short','password_confirmation':'short'},
                        {'password_confirmation':'mismatch'}, {'admin_password':[]}, {'password':''}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.reset_password(**changes).status_code, 400)
        self.reader.refresh_from_db(); self.assertTrue(self.reader.check_password(PASSWORD))
        self.assertFalse(RegistroAuditoria.objects.filter(acao='senha_redefinida').exists())
        client = Client(enforce_csrf_checks=True); client.force_login(self.admin)
        self.assertEqual(self.reset_password(client=client).status_code, 403)
        client = Client(); client.force_login(self.reader)
        self.assertEqual(self.reset_password(client=client).status_code, 403)
        client.logout(); self.assertEqual(self.reset_password(client=client).status_code, 401)

    def test_reset_throttle_is_shared_across_targets(self):
        for _ in range(5):
            self.assertEqual(self.reset_password(admin_password='wrong').status_code, 400)
        self.assertEqual(self.reset_password(target=self.admin).status_code, 429)

    def test_staff_cannot_reset_superuser_and_self_reset_requires_new_login(self):
        staff = Usuario.objects.create_user('staff@example.org', PASSWORD, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.reset_password(target=self.admin).status_code, 403)
        self.client.force_login(self.admin)
        response = self.reset_password(target=self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['login_required'])
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)


class ExportTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user('viewer@example.org', PASSWORD)
        self.client.force_login(self.user)
        self.lot = self.make_lot('3550308', [0, None, 15])
        self.params = {'codigo':'3550308','agravo':'dengue','indicador':'infodengue_dengue'}

    def make_lot(self, code, counts, indicator='infodengue_dengue', suffix=''):
        from .indicators import REGIONS
        territory, _ = RecorteGeografico.objects.get_or_create(tipo='municipio', codigo=code, defaults={'nome':REGIONS[code]['nome'],'uf':'SP'})
        disease = indicator.replace('infodengue_', '')
        source = FonteEpidemiologica.objects.create(nome='Fonte'+suffix, tipo='json', indicador=indicator, recorte=territory,
            url=f'https://info.dengue.mat.br/api/alertcity?geocode={code}&disease={disease}&format=json&ew_start=1&ew_end=52&ey_start=2024&ey_end=2024')
        rows = [{'SE':202401+i,'data_iniSE':int(datetime.combine(week_start(2024,i+1),time(),tzinfo=timezone.utc).timestamp()*1000),
                 'casos':v,'casos_est':v,'municipio_nome':territory.nome,'id':int(code+str(202401+i)+'00001')} for i,v in enumerate(counts)]
        lot = LoteColeta.objects.create(fonte=source, indicador=indicator, adaptador='infodengue', agravo=disease,
            url_origem=source.url, territorio_codigo=code, sha256='a'*64, sha256_original='b'*64,
            dados_brutos=rows, quantidade_registros=len(rows))
        self.assertEqual(process_lote(lot.pk).status, 'sucesso')
        return lot

    def export(self, **overrides):
        return self.client.get('/api/indicadores/exportar/', {**self.params, **overrides})

    def test_csv_preserves_zero_null_filters_and_provenance(self):
        response = self.export(inicio='2023-12-31', fim='2024-01-07')
        self.assertEqual(response.status_code, 200, response.content)
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual([r['casos'] for r in rows], ['0',''])
        self.assertEqual(rows[0]['indicador'], 'infodengue_dengue')
        self.assertIn(self.lot.url_origem, rows[0]['fontes_e_lotes'])
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(RegistroAuditoria.objects.get().acao, 'dados_exportados')

    def test_json_aggregate_matches_dashboard(self):
        data = self.export(formato='json').json()
        panel = self.client.get('/api/indicadores/', self.params).json()
        self.assertEqual(data['registros'], panel['serie'])
        self.assertEqual(data['metadados']['fontes'], panel['fontes'])

    def test_raw_filters_original_rows_and_does_not_mix_diseases(self):
        self.make_lot('3550308', [999,999,999], indicator='infodengue_zika')
        response = self.export(modo='brutos', formato='json', inicio='2024-01-14', fim='2024-01-14')
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()['registros']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['registro_bruto'], self.lot.dados_brutos[2])
        self.assertEqual(rows[0]['lote_id'], self.lot.pk)

    def test_region_exports_municipal_rows_without_aggregation_in_raw_mode(self):
        from .indicators import REGIONS
        region = REGIONS['3550308']['regiao_codigo']
        code = next(c for c,v in REGIONS.items() if c!='3550308' and v['regiao_codigo']==region)
        self.make_lot(code, [2,3,4])
        aggregated = self.export(tipo='regiao', codigo=region, formato='json').json()
        self.assertEqual([r['casos'] for r in aggregated['registros']], [2,None,19])
        raw = self.export(tipo='regiao', codigo=region, modo='brutos', formato='json').json()
        self.assertEqual(len(raw['registros']), 6)
        self.assertEqual({r['municipio_ibge'] for r in raw['registros']}, {code,'3550308'})

    def test_invalid_modes_empty_periods_and_permissions(self):
        for params in [{'modo':'brutos','formato':'csv'}, {'formato':'html'}, {'codigo':'x'},
                       {'inicio':'invalid'}, {'inicio':'2025-01-01','fim':'2025-02-01'}]:
            self.assertEqual(self.export(**params).status_code, 400)
        restricted = PerfilAcesso.objects.create(nome='Sem exportação', permissoes=[])
        self.user.perfil=restricted; self.user.save()
        self.assertEqual(self.export().status_code, 403)
        self.client.logout(); self.assertEqual(self.export().status_code, 401)

    def test_export_limits_and_formula_escaping(self):
        from .exports import csv_cell
        self.assertEqual(csv_cell('  =1+1'), "'  =1+1")
        self.assertEqual(csv_cell('@SUM(1)'), "'@SUM(1)")
        with patch('sme.exports.MAX_ROWS', 1):
            self.assertEqual(self.export().status_code, 400)
            self.assertEqual(self.export(modo='brutos', formato='json').status_code, 400)
        with patch('sme.exports.MAX_BYTES', 10):
            self.assertEqual(self.export().status_code, 413)
        self.assertFalse(RegistroAuditoria.objects.exists())

    def test_infogripe_raw_keeps_original_columns(self):
        from .test_multi_provider import respiratory_row, csv_bytes
        from .datasets import INFOGRIPE_URL
        from .collection import collect_source
        source = FonteEpidemiologica.objects.create(nome='SRAG', tipo='csv', indicador='infogripe_srag',
            url=INFOGRIPE_URL, recorte=self.lot.fonte.recorte)
        raw = respiratory_row()
        with patch('sme.infogripe.fetch_public', return_value=(csv_bytes([raw]), {})):
            run = collect_source(source.pk)
        self.assertEqual(run.status, 'sucesso')
        result = self.export(agravo='srag', indicador='infogripe_srag', modo='brutos', formato='json').json()
        self.assertEqual(result['registros'][0]['registro_bruto'], raw)
        self.assertEqual(len(result['registros']), 1)

    def test_sivep_week_53_and_missing_rows_are_exported(self):
        from .test_sivep import workbook_bytes
        from .datasets import SIVEP_URL
        from .collection import collect_source
        territory = RecorteGeografico.objects.create(tipo='municipio',codigo='3510500',nome='Caraguatatuba',uf='SP')
        source = FonteEpidemiologica.objects.create(nome='SIVEP',tipo='xlsx',indicador='sivep_srag',
            url=SIVEP_URL+'?ano=2025',recorte=territory)
        with patch('sme.sivep.fetch_public', side_effect=[(b'[{"name":"2025","type":"tree"}]', {}), (workbook_bytes(), {})]):
            run = collect_source(source.pk)
        self.assertEqual(run.status, 'sucesso', run.mensagem)
        data = self.export(codigo='3510500',agravo='srag',indicador='sivep_srag',modo='brutos',formato='json').json()
        self.assertEqual(len(data['registros']), 53)
        self.assertIsNone(data['registros'][1]['registro_bruto']['casos'])
        self.assertEqual(data['registros'][-1]['registro_bruto']['semana'], 53)
        self.assertEqual(data['registros'][-1]['registro_bruto']['casos'], 7)


from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SprintThreeMigrationTests(TransactionTestCase):
    def test_existing_users_keep_password_status_and_roles(self):
        previous = [('sme','0005_arquivocoleta_alter_fonteepidemiologica_tipo_and_more')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            User = apps.get_model('sme','Usuario')
            admin = User.objects.create(email='migration-admin@example.org',is_staff=True,is_superuser=True,password='original-hash')
            reader = User.objects.create(email='migration-reader@example.org',is_active=False,password='reader-hash')
        finally:
            MigrationExecutor(connection).migrate(latest)
        migrated = Usuario.objects.get(pk=admin.pk)
        self.assertEqual(migrated.password, 'original-hash')
        self.assertEqual(migrated.perfil.codigo, 'administrador')
        self.assertTrue(migrated.is_superuser)
        migrated = Usuario.objects.get(pk=reader.pk)
        self.assertEqual(migrated.password, 'reader-hash')
        self.assertFalse(migrated.is_active)
        self.assertEqual(migrated.perfil.codigo, 'usuario')
