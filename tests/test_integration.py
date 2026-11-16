"""Execute: python -m unittest discover -s tests -v"""
import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as project

class IntegrationTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory()
  project.DB=Path(cls.temp.name)/'test.db'
  project.init_db()
  project.app.config.update(TESTING=True,SECRET_KEY='test-only-key')
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def setUp(self):
  self.client=project.app.test_client()
  with project.db() as d:
   for t in ['completions','quiz_attempts','certificates','saved_jobs','posts','users']:d.execute('DELETE FROM '+t)
 def login(self):
  x=self.client.post('/auth/register',json={'name':'Aluna Teste','email':'aluna@exemplo.com','password':'SenhaSegura123'});self.assertEqual(x.status_code,200)
 def test_pages_and_catalog(self):
  for path in ['/dashboard','/cursos','/perfil','/certificados','/tutora','/laboratorio','/oportunidades','/comunidade']:
   self.assertEqual(self.client.get(path).status_code,200,path)
  x=self.client.get('/data/courses').get_json();self.assertGreaterEqual(len(x),15)
 def test_auth_and_progress(self):
  self.login();lid=project.COURSES['ux']['lessons'][0]['id'];correct=project.COURSES['ux']['lessons'][0]['correct']
  self.assertEqual(self.client.post('/data/lesson/'+lid+'/answer',json={'choice':correct}).status_code,200)
  self.assertEqual(self.client.get('/data/stats').get_json()['completed'],1)
  self.client.post('/auth/logout');self.assertEqual(self.client.get('/data/stats').get_json()['completed'],0)
  self.assertEqual(self.client.post('/auth/login',json={'email':'aluna@exemplo.com','password':'SenhaSegura123'}).status_code,200)
  self.assertEqual(self.client.get('/data/stats').get_json()['completed'],1)
 def test_certificate_lock_and_pdf(self):
  self.login();cid='ux';r=self.client.post('/data/certificate/'+cid,json={});self.assertEqual(r.status_code,400)
  for lesson in project.COURSES[cid]['lessons']:
   r=self.client.post('/data/lesson/'+lesson['id']+'/answer',json={'choice':lesson['correct']});self.assertTrue(r.get_json()['correct'])
  r=self.client.post('/data/certificate/'+cid,json={});self.assertEqual(r.status_code,200);code=r.get_json()['code']
  pdf=self.client.get('/certificado/pdf/'+code);self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.data.startswith(b'%PDF'))
  self.assertTrue(self.client.get('/data/verify/'+code).get_json()['valid'])
 def test_plan_persists_and_resumes(self):
  self.login()
  x=self.client.post('/data/plan',json={'goal':'ux','level':'iniciante','hours_per_week':3,'course_ids':['ux','access']})
  self.assertEqual(x.status_code,200,x.get_json())
  p=x.get_json()['plan'];self.assertEqual(len(p['courses']),2);self.assertEqual(p['done'],0)
  self.assertTrue(p['next']);self.assertTrue(p['weeks'])
  lid=project.COURSES['ux']['lessons'][0]['id'];correct=project.COURSES['ux']['lessons'][0]['correct']
  self.client.post('/data/lesson/'+lid+'/answer',json={'choice':correct})
  p=self.client.get('/data/plan').get_json()['plan'];self.assertEqual(p['done'],1)
  self.assertNotEqual(p['next']['id'],lid)
  self.client.post('/auth/logout');self.client.post('/auth/login',json={'email':'aluna@exemplo.com','password':'SenhaSegura123'})
  self.assertEqual(self.client.get('/data/plan').get_json()['plan']['done'],1)
  self.assertEqual(self.client.delete('/data/plan').status_code,200)
  self.assertIsNone(self.client.get('/data/plan').get_json()['plan'])
  self.assertEqual(self.client.get('/data/stats').get_json()['completed'],1)
 def test_plan_rejects_invalid_courses(self):
  self.login()
  r=self.client.post('/data/plan',json={'course_ids':['inexistente'],'hours_per_week':3})
  self.assertEqual(r.status_code,400)
 def test_tutor_fallback(self):
  key=os.environ.pop('OPENAI_API_KEY',None)
  try:
   r=self.client.post('/api/tutor',json={'pergunta':'O que é Python?'});self.assertEqual(r.status_code,200);self.assertTrue(r.get_json()['answer'])
  finally:
   if key is not None:os.environ['OPENAI_API_KEY']=key
 def test_community_and_jobs(self):
  self.login();self.assertEqual(self.client.post('/data/posts',json={'body':'Aprendi HTML!'}).status_code,200)
  self.assertEqual(len(self.client.get('/data/posts').get_json()),1)
  self.assertTrue(self.client.post('/data/jobs/1/save',json={}).get_json()['saved'])
if __name__=='__main__':unittest.main()
