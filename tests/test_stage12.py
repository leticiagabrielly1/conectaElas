import unittest, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as project

class Stage12Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();project.DB=Path(cls.tmp.name)/'db.sqlite';project.init_db();project.app.config.update(TESTING=True,SECRET_KEY='test-secret')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):self.client=project.app.test_client()
 def test_admin_requires_auth_and_role(self):
  self.assertEqual(self.client.get('/data/admin/overview').status_code,401)
  self.assertEqual(self.client.post('/auth/register',json={'name':'Aluna','email':'aluna12@example.com','password':'SenhaSegura123'}).status_code,200)
  self.assertEqual(self.client.get('/data/admin/overview').status_code,403)
 def test_password_recovery_generic_without_smtp(self):
  r=self.client.post('/auth/password/forgot',json={'email':'unknown@example.com'})
  self.assertEqual(r.status_code,200);self.assertTrue(r.get_json()['ok'])
  self.assertEqual(self.client.post('/auth/password/reset',json={'token':'invalid','password':'NovaSenhaSegura123'}).status_code,400)
 def test_certificate_requires_login(self):
  self.assertEqual(self.client.post('/data/certificate/ux',json={}).status_code,401)
 def test_code_start_catalog_present(self):
  self.assertGreaterEqual(len(self.client.get('/data/courses').get_json()),15)
