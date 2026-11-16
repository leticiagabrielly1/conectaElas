import os, sqlite3, json, secrets, hashlib, smtplib, ssl
from email.message import EmailMessage
from datetime import timedelta
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from flask import url_for
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parent
app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY','local-development-only-change-me')
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','0')=='1',MAX_CONTENT_LENGTH=1_000_000)
DB=ROOT/'conectas.db'
CURRICULUM=json.loads((ROOT/'curriculo.json').read_text(encoding='utf-8'))
COURSES={c['id']:c for c in CURRICULUM['courses']}
LESSONS={l['id']:(c,l) for c in CURRICULUM['courses'] for l in c['lessons']}

def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init_db():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS completions(user_id INTEGER NOT NULL REFERENCES users(id),lesson_id TEXT NOT NULL,completed_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,lesson_id));
  CREATE TABLE IF NOT EXISTS quiz_attempts(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),lesson_id TEXT NOT NULL,correct INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS certificates(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),course_id TEXT NOT NULL,code TEXT UNIQUE NOT NULL,issued_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,course_id));
  CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,title TEXT NOT NULL,organization TEXT NOT NULL,mode TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS saved_jobs(user_id INTEGER NOT NULL REFERENCES users(id),job_id INTEGER NOT NULL REFERENCES jobs(id),PRIMARY KEY(user_id,job_id));
  CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),body TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS module_assessments(user_id INTEGER NOT NULL REFERENCES users(id),course_id TEXT NOT NULL,module TEXT NOT NULL,passed_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,course_id,module));
  CREATE TABLE IF NOT EXISTS course_favorites(user_id INTEGER NOT NULL REFERENCES users(id),course_id TEXT NOT NULL,PRIMARY KEY(user_id,course_id));
  CREATE TABLE IF NOT EXISTS tutor_messages(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, role TEXT NOT NULL CHECK(role IN ('user','assistant')), body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE INDEX IF NOT EXISTS tutor_messages_user_idx ON tutor_messages(user_id,id);
  CREATE TABLE IF NOT EXISTS editor_projects(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT NOT NULL,language TEXT NOT NULL,code TEXT NOT NULL,lesson_id TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE INDEX IF NOT EXISTS editor_projects_owner ON editor_projects(user_id,id);
  CREATE TABLE IF NOT EXISTS editor_challenge_attempts(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),challenge_id TEXT NOT NULL,passed INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS weekly_goals(user_id INTEGER PRIMARY KEY REFERENCES users(id),target INTEGER NOT NULL CHECK(target BETWEEN 1 AND 100),updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS portfolio_items(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT NOT NULL,description TEXT NOT NULL,technologies TEXT NOT NULL,project_url TEXT NOT NULL DEFAULT '',course_id TEXT NOT NULL DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS password_reset_tokens(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at TEXT NOT NULL,used_at TEXT);
  CREATE TABLE IF NOT EXISTS study_plans(user_id INTEGER PRIMARY KEY REFERENCES users(id),goal TEXT NOT NULL,level TEXT NOT NULL,hours_per_week INTEGER NOT NULL,course_ids TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
  c.executescript("""CREATE TABLE IF NOT EXISTS community_comments(id INTEGER PRIMARY KEY,post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id),body TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS community_likes(post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id),PRIMARY KEY(post_id,user_id));
  CREATE TABLE IF NOT EXISTS community_reports(id INTEGER PRIMARY KEY,post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,comment_id INTEGER REFERENCES community_comments(id) ON DELETE CASCADE,reporter_id INTEGER NOT NULL REFERENCES users(id),reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP, CHECK((post_id IS NOT NULL) != (comment_id IS NOT NULL)));
  CREATE TABLE IF NOT EXISTS community_moderators(user_id INTEGER PRIMARY KEY REFERENCES users(id));
  CREATE INDEX IF NOT EXISTS community_reports_status ON community_reports(status);""")
  c.executescript("""CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE);
  CREATE TABLE IF NOT EXISTS admin_course_data(course_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS admin_audit(id INTEGER PRIMARY KEY,admin_id INTEGER REFERENCES users(id),action TEXT NOT NULL,entity TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS certificate_revocations(code TEXT PRIMARY KEY REFERENCES certificates(code),reason TEXT NOT NULL,revoked_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS course_views(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),course_id TEXT NOT NULL,viewed_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE INDEX IF NOT EXISTS course_views_course ON course_views(course_id);""")

  columns={r['name'] for r in c.execute('PRAGMA table_info(posts)')}
  if 'topic' not in columns:c.execute("ALTER TABLE posts ADD COLUMN topic TEXT NOT NULL DEFAULT 'Geral'")
  if 'kind' not in columns:c.execute("ALTER TABLE posts ADD COLUMN kind TEXT NOT NULL DEFAULT 'discussao'")
  if 'hidden' not in columns:c.execute('ALTER TABLE posts ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')
  if not c.execute('SELECT 1 FROM jobs').fetchone():
   c.executemany('INSERT INTO jobs(title,organization,mode,category,description) VALUES(?,?,?,?,?)',[
    ('Estágio em Front-end','Empresa ilustrativa','Remoto','Estágio','Exemplo de vaga para desenvolver interfaces HTML, CSS e JavaScript.'),('Jovem Aprendiz em TI','Organização ilustrativa','Presencial','Jovem Aprendiz','Exemplo de programa de aprendizagem para estudantes.'),('Projeto de Portfólio Web','Comunidade ilustrativa','Remoto','Projeto','Desafio de construir um site acessível para seu portfólio.')])
init_db()
def load_admin_courses():
 with db() as c:
  for row in c.execute('SELECT course_id,payload FROM admin_course_data'):
   try:
    course=json.loads(row['payload']); COURSES[row['course_id']]=course
   except (ValueError,KeyError):continue
 LESSONS.clear();LESSONS.update({l['id']:(c,l) for c in COURSES.values() for l in c['lessons']})
load_admin_courses()
from codestart_engine import bp
app.register_blueprint(bp)

def auth_required(fn):
 @wraps(fn)
 def wrap(*a,**kw):
  if not session.get('uid'):return jsonify(error='Faça login para continuar.'),401
  return fn(*a,**kw)
 return wrap

def data():return request.get_json(silent=True) or {}
def error(s,code=400):return jsonify(error=s),code

def user():
 if not session.get('uid'):return None
 with db() as c:r=c.execute('SELECT id,name,email FROM users WHERE id=?',(session['uid'],)).fetchone()
 return dict(r) if r else None

PAGES={'/':'dashboard','/dashboard':'dashboard','/cursos':'courses','/desafios':'challenges','/perfil':'profile','/certificados':'certificates','/oportunidades':'jobs','/portfolio':'portfolio','/comunidade':'community','/laboratorio':'lab','/tutora':'tutor','/entrar':'auth','/projetos':'projects','/trilha-personalizada':'planner','/administracao':'admin'}
for path,pg in PAGES.items():
 def view(pg=pg):return render_template('page.html',page=pg)
 app.add_url_rule(path,endpoint='page_'+pg+'_'+path.replace('/','_'),view_func=view)
@app.get('/curso/<cid>')
def course_page(cid):
 if cid not in COURSES:return 'Curso não encontrado',404
 with db() as c:c.execute('INSERT INTO course_views(user_id,course_id) VALUES(?,?)',(session.get('uid'),cid))
 return render_template('page.html',page='course',course_id=cid)
@app.get('/certificado/verificar/<code>')
def verify_page(code):return render_template('page.html',page='verify',verify_code=code)

@app.post('/auth/register')
def register():
 x=data();name=str(x.get('name','')).strip();email=str(x.get('email','')).strip().lower();pw=str(x.get('password',''))
 if len(name)<2 or len(name)>90 or '@' not in email or len(pw)<8:return error('Informe nome, e-mail válido e senha com pelo menos 8 caracteres.')
 try:
  with db() as c:
   r=c.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(name,email,generate_password_hash(pw)));uid=r.lastrowid
 except sqlite3.IntegrityError:return error('E-mail já cadastrado.')
 session.clear();session['uid']=uid;return jsonify(ok=True)
@app.post('/auth/login')
def login():
 x=data()
 with db() as c:r=c.execute('SELECT * FROM users WHERE email=?',(str(x.get('email','')).strip().lower(),)).fetchone()
 if not r or not check_password_hash(r['password'],str(x.get('password',''))):return error('E-mail ou senha incorretos.',401)
 session.clear();session['uid']=r['id'];return jsonify(ok=True)
def send_password_reset(email, link):
 host=os.getenv('SMTP_HOST','').strip()
 if not host:return False
 msg=EmailMessage();msg['Subject']='ConectasElas — redefinir senha';msg['From']=os.environ['SMTP_FROM'];msg['To']=email
 msg.set_content('Para redefinir sua senha, acesse o link abaixo (válido por 30 minutos):\n'+link+'\nSe não solicitou, ignore esta mensagem.')
 with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=12) as server:
  server.starttls(context=ssl.create_default_context())
  server.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
  server.send_message(msg)
 return True

@app.post('/auth/password/forgot')
def forgot_password():
 email=str(data().get('email','')).strip().lower()
 generic=jsonify(ok=True,message='Se a conta existir e o e-mail estiver configurado, enviaremos instruções.')
 if not os.getenv('SMTP_HOST'):return generic
 with db() as d:
  row=d.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
  if not row:return generic
  token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
  expiry=(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()
  d.execute('DELETE FROM password_reset_tokens WHERE user_id=?',(row['id'],))
  d.execute('INSERT INTO password_reset_tokens(token_hash,user_id,expires_at) VALUES(?,?,?)',(digest,row['id'],expiry))
 base=os.getenv('PUBLIC_BASE_URL',request.host_url.rstrip('/')).rstrip('/')
 try:send_password_reset(email,base+'/entrar?reset_token='+token)
 except (OSError,smtplib.SMTPException,KeyError):app.logger.exception('Falha ao enviar e-mail de recuperação')
 return generic

@app.post('/auth/password/reset')
def reset_password():
 x=data();token=str(x.get('token',''));password=str(x.get('password',''))
 if not 12<=len(password)<=128 or len(token)>256:return error('Informe uma senha de 12 a 128 caracteres e um token válido.')
 digest=hashlib.sha256(token.encode()).hexdigest()
 with db() as d:
  row=d.execute('SELECT user_id,expires_at,used_at FROM password_reset_tokens WHERE token_hash=?',(digest,)).fetchone()
  if not row or row['used_at'] or datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc):return error('Link inválido ou expirado.',400)
  d.execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(password),row['user_id']))
  d.execute('UPDATE password_reset_tokens SET used_at=? WHERE token_hash=?',(datetime.now(timezone.utc).isoformat(),digest))
 session.clear()
 return jsonify(ok=True)

@app.post('/auth/logout')
def logout():session.clear();return jsonify(ok=True)
@app.get('/data/me')
def me():return jsonify(user=user())
@app.post('/data/profile')
@auth_required
def profile_update():
 name=str(data().get('name','')).strip()
 if not 2<=len(name)<=90:return error('Nome deve ter de 2 a 90 caracteres.')
 with db() as c:c.execute('UPDATE users SET name=? WHERE id=?',(name,session['uid']))
 return jsonify(ok=True)
@app.get('/data/courses')
def courses():
 with db() as c:
  done={r['lesson_id'] for r in c.execute('SELECT lesson_id FROM completions WHERE user_id=?',(session.get('uid',-1),))}
  favorites={r['course_id'] for r in c.execute('SELECT course_id FROM course_favorites WHERE user_id=?',(session.get('uid',-1),))}
 return jsonify([dict(id=x['id'],name=x['name'],description=x['description'],level=x['level'],category=x.get('category','Geral'),hours=x.get('hours',0),favorite=x['id'] in favorites,total=len(x['lessons']),done=sum(l['id'] in done for l in x['lessons'])) for x in COURSES.values()])
@app.post('/data/courses/<cid>/favorite')
@auth_required
def favorite_course(cid):
 if cid not in COURSES:return error('Curso não encontrado.',404)
 with db() as c:
  row=c.execute('SELECT 1 FROM course_favorites WHERE user_id=? AND course_id=?',(session['uid'],cid)).fetchone()
  if row:c.execute('DELETE FROM course_favorites WHERE user_id=? AND course_id=?',(session['uid'],cid))
  else:c.execute('INSERT INTO course_favorites(user_id,course_id) VALUES(?,?)',(session['uid'],cid))
 return jsonify(favorite=not bool(row))

def module_groups(course):
 groups=[]
 for lesson in course['lessons']:
  name=lesson.get('module','Módulo')
  if not groups or groups[-1][0]!=name:groups.append((name,[]))
  groups[-1][1].append(lesson)
 return groups

def access_state(cid,uid):
 course=COURSES[cid];groups=module_groups(course)
 with db() as d:
  done={r['lesson_id'] for r in d.execute('SELECT lesson_id FROM completions WHERE user_id=?',(uid,))}
  passed={r['module'] for r in d.execute('SELECT module FROM module_assessments WHERE user_id=? AND course_id=?',(uid,cid))}
 states={};unlocked=True
 for name,lessons in groups:
  states[name]={'unlocked':unlocked,'passed':name in passed,'done':sum(l['id'] in done for l in lessons),'total':len(lessons)}
  unlocked=unlocked and name in passed
 return states,done

@app.get('/data/course/<cid>/modules')
def course_modules(cid):
 if cid not in COURSES:return error('Curso não encontrado.',404)
 states,_=access_state(cid,session.get('uid',-1))
 return jsonify([{'name':name,**states[name]} for name,_ in module_groups(COURSES[cid])])

@app.post('/data/course/<cid>/module/assessment')
@auth_required
def assess_module(cid):
 if cid not in COURSES:return error('Curso não encontrado.',404)
 name=data().get('module');choice=data().get('choice');groups=dict(module_groups(COURSES[cid]))
 if name not in groups:return error('Módulo inválido.')
 states,done=access_state(cid,session['uid'])
 if not states[name]['unlocked']:return error('Conclua o módulo anterior primeiro.',403)
 lessons=groups[name]
 if any(l['id'] not in done for l in lessons):return error('Conclua todas as aulas deste módulo antes da avaliação.',403)
 last=lessons[-1]
 if not isinstance(choice,int) or isinstance(choice,bool) or not 0<=choice<len(last.get('options',[])):return error('Escolha uma alternativa válida.')
 good=choice==last.get('correct')
 with db() as d:
  d.execute('INSERT INTO quiz_attempts(user_id,lesson_id,correct) VALUES(?,?,?)',(session['uid'],last['id'],int(good)))
  if good:d.execute('INSERT OR IGNORE INTO module_assessments(user_id,course_id,module) VALUES(?,?,?)',(session['uid'],cid,name))
 return jsonify(correct=good,message='Avaliação aprovada! Próximo módulo desbloqueado.' if good else 'Revise o conteúdo e tente novamente.',explanation=last.get('quizExplanation',''))

@app.get('/data/course/<cid>')
def course_data(cid):
 if cid not in COURSES:return error('Curso não encontrado.',404)
 c=COURSES[cid]
 with db() as d:done={r['lesson_id'] for r in d.execute('SELECT lesson_id FROM completions WHERE user_id=?',(session.get('uid',-1),))}
 states,_=access_state(cid,session.get('uid',-1))
 return jsonify(id=cid,name=c['name'],description=c['description'],level=c['level'],category=c.get('category','Geral'),hours=c.get('hours',0),finalProject=c.get('finalProject'),modules=[{'name':n,**states[n]} for n,_ in module_groups(c)],lessons=[dict(id=l['id'],title=l['title'],module=l.get('module','Módulo'),completed=l['id'] in done,locked=not states[l.get('module','Módulo')]['unlocked']) for l in c['lessons']])
@app.get('/data/lesson/<lid>')
def lesson_data(lid):
 if lid not in LESSONS:return error('Aula não encontrada.',404)
 c,l=LESSONS[lid]
 states,_=access_state(c['id'],session.get('uid',-1))
 if not states[l.get('module','Módulo')]['unlocked']:return error('Este módulo ainda está bloqueado.',403)
 return jsonify(course=c['id'],title=l['title'],module=l.get('module',''),body=l.get('body',''),theory=l.get('theory',[]),objectives=l.get('objectives',[]),practice=l.get('practice',''),challenge=l.get('challenge',''),question=l.get('question',''),options=l.get('options',[]),hints=l.get('hints',[]),codeLines=l.get('codeLines',[]),explanation=l.get('quizExplanation',''))
@app.post('/data/lesson/<lid>/answer')
@auth_required
def answer(lid):
 if lid not in LESSONS:return error('Aula não encontrada.',404)
 c,l=LESSONS[lid];choice=data().get('choice');correct=l.get('correct')
 states,_=access_state(c['id'],session['uid'])
 if not states[l.get('module','Módulo')]['unlocked']:return error('Este módulo ainda está bloqueado.',403)
 if not isinstance(choice,int) or isinstance(choice,bool) or not 0<=choice<len(l.get('options',[])):return error('Selecione uma alternativa válida.')
 good=choice==correct
 with db() as d:
  d.execute('INSERT INTO quiz_attempts(user_id,lesson_id,correct) VALUES(?,?,?)',(session['uid'],lid,int(good)))
  if good:d.execute('INSERT OR IGNORE INTO completions(user_id,lesson_id) VALUES(?,?)',(session['uid'],lid))
 return jsonify(correct=good,explanation=l.get('quizExplanation',''),message='Aula concluída!' if good else 'Revise a explicação e tente novamente.')
@app.get('/data/plan')
@auth_required
def get_study_plan():
 with db() as d:
  row=d.execute('SELECT * FROM study_plans WHERE user_id=?',(session['uid'],)).fetchone()
 if not row:return jsonify(plan=None)
 return jsonify(plan=plan_details(dict(row)))

def plan_details(row):
 ids=[cid for cid in json.loads(row['course_ids']) if cid in COURSES]
 with db() as d:
  completed={r['lesson_id'] for r in d.execute('SELECT lesson_id FROM completions WHERE user_id=?',(row['user_id'],))}
 courses=[];remaining=[]
 for cid in ids:
  c=COURSES[cid];ls=c['lessons'];done=sum(l['id'] in completed for l in ls)
  next_lesson=next((l for l in ls if l['id'] not in completed),None)
  courses.append({'id':cid,'name':c['name'],'level':c['level'],'total':len(ls),'done':done,'percent':round(100*done/len(ls)) if ls else 100,'next_lesson':next_lesson['id'] if next_lesson else None,'next_title':next_lesson['title'] if next_lesson else None})
  remaining.extend([{'id':l['id'],'title':l['title'],'course_id':cid,'course_name':c['name'],'module':l.get('module','Módulo')} for l in ls if l['id'] not in completed])
 total=sum(c['total'] for c in courses);done=sum(c['done'] for c in courses)
 hours=row['hours_per_week'];per_week=max(1,round(hours*60/35));weeks=[]
 for i in range(min(8,(len(remaining)+per_week-1)//per_week)):
  chunk=remaining[i*per_week:(i+1)*per_week]
  weeks.append({'number':i+1,'lessons':chunk,'count':len(chunk),'minutes':len(chunk)*35})
 return {'goal':row['goal'],'level':row['level'],'hours_per_week':hours,'courses':courses,'total':total,'done':done,'percent':round(100*done/total) if total else 0,'remaining':len(remaining),'estimated_weeks':(len(remaining)+per_week-1)//per_week,'lessons_per_week':per_week,'next':remaining[0] if remaining else None,'weeks':weeks,'created_at':row['created_at']}

@app.post('/data/plan')
@auth_required
def save_study_plan():
 x=data();ids=x.get('course_ids',[])
 if not isinstance(ids,list) or not ids or len(ids)>15 or any(not isinstance(i,str) or i not in COURSES for i in ids):return error('Escolha uma trilha válida.')
 ids=list(dict.fromkeys(ids));goal=str(x.get('goal','')).strip()[:100];level=str(x.get('level','iniciante'))[:30]
 try:hours=int(x.get('hours_per_week',5))
 except (ValueError,TypeError):return error('Informe horas válidas.')
 if hours<1 or hours>40:return error('Escolha entre 1 e 40 horas por semana.')
 with db() as d:
  d.execute("""INSERT INTO study_plans(user_id,goal,level,hours_per_week,course_ids) VALUES(?,?,?,?,?)
  ON CONFLICT(user_id) DO UPDATE SET goal=excluded.goal,level=excluded.level,hours_per_week=excluded.hours_per_week,course_ids=excluded.course_ids,updated_at=CURRENT_TIMESTAMP""",(session['uid'],goal,level,hours,json.dumps(ids)))
 return get_study_plan()

@app.delete('/data/plan')
@auth_required
def delete_study_plan():
 with db() as d:d.execute('DELETE FROM study_plans WHERE user_id=?',(session['uid'],))
 return jsonify(ok=True)

@app.get('/data/stats')
def stats():
 uid=session.get('uid',-1)
 with db() as d:
  completed=[dict(r) for r in d.execute('SELECT lesson_id,completed_at FROM completions WHERE user_id=?',(uid,))]
  attempts=[dict(r) for r in d.execute('SELECT correct,created_at FROM quiz_attempts WHERE user_id=?',(uid,))]
  certificates=d.execute('SELECT COUNT(*) FROM certificates WHERE user_id=?',(uid,)).fetchone()[0]
 per=[dict(id=c['id'],name=c['name'],done=sum(x['lesson_id'] in {l['id'] for l in c['lessons']} for x in completed),total=len(c['lessons'])) for c in COURSES.values()]
 weekly={}
 for x in completed:
  key=x['completed_at'][:10];weekly[key]=weekly.get(key,0)+1
 return jsonify(completed=len(completed),total=len(LESSONS),xp=len(completed)*20+sum(x['correct'] for x in attempts)*5,attempts=len(attempts),accuracy=round(100*sum(x['correct'] for x in attempts)/len(attempts)) if attempts else 0,certificates=certificates,per_course=per,activity=[{'date':k,'count':v} for k,v in sorted(weekly.items())][-14:])
@app.get('/data/performance')
@auth_required
def performance():
 from datetime import date,timedelta
 uid=session['uid'];today=date.today()
 with db() as d:
  lessons=[dict(r) for r in d.execute('SELECT lesson_id,completed_at FROM completions WHERE user_id=?',(uid,))]
  quizzes=[dict(r) for r in d.execute('SELECT correct,created_at FROM quiz_attempts WHERE user_id=?',(uid,))]
  challenges=[dict(r) for r in d.execute('SELECT passed,created_at FROM editor_challenge_attempts WHERE user_id=?',(uid,))]
  certs=[dict(r) for r in d.execute('SELECT course_id,code,issued_at FROM certificates WHERE user_id=? ORDER BY issued_at DESC',(uid,))]
  goal=d.execute('SELECT target FROM weekly_goals WHERE user_id=?',(uid,)).fetchone()
  plan=d.execute('SELECT course_ids FROM study_plans WHERE user_id=?',(uid,)).fetchone()
 done={x['lesson_id'] for x in lessons}
 initiated=[];finished=[];languages=[]
 for course in COURSES.values():
  ids={x['id'] for x in course['lessons']};n=len(done&ids)
  if n:initiated.append(course['id'])
  if ids and n==len(ids):finished.append(course['id'])
  if n:languages.append(dict(name=course['name'],done=n,total=len(ids),percent=round(n/len(ids)*100)))
 events=[x['completed_at'][:10] for x in lessons]+[x['created_at'][:10] for x in quizzes]+[x['created_at'][:10] for x in challenges]
 days=set(events)
 streak=0;cursor=today
 if cursor.isoformat() not in days:cursor-=timedelta(days=1)
 while cursor.isoformat() in days:streak+=1;cursor-=timedelta(days=1)
 week_start=today-timedelta(days=today.weekday())
 weekly=[dict(date=(week_start+timedelta(days=i)).isoformat(),count=events.count((week_start+timedelta(days=i)).isoformat())) for i in range(7)]
 months=[]
 for i in range(5,-1,-1):
  year=today.year;month=today.month-i
  while month<=0:month+=12;year-=1
  key=f'{year:04d}-{month:02d}';months.append(dict(month=key,count=sum(x.startswith(key) for x in events)))
 correct=sum(bool(x['correct']) for x in quizzes)+sum(bool(x['passed']) for x in challenges)
 incorrect=len(quizzes)+len(challenges)-correct
 xp=len(lessons)*20+sum(bool(x['correct']) for x in quizzes)*5
 level=xp//200+1
 achievements=[]
 for label,condition in [('Primeira aula',len(lessons)>=1),('10 aulas concluídas',len(lessons)>=10),('Primeiro certificado',bool(certs)),('7 dias seguidos',streak>=7),('1000 XP',xp>=1000)]:
  achievements.append(dict(name=label,unlocked=condition))
 target=goal['target'] if goal else 5
 week_lessons=sum(x['completed_at'][:10]>=week_start.isoformat() for x in lessons)
 return jsonify(courses_started=len(initiated),courses_completed=len(finished),weekly=weekly,monthly=months,languages=languages,correct=correct,incorrect=incorrect,xp=xp,level=level,achievements=achievements,streak=streak,weekly_goal=target,weekly_done=week_lessons,certificates=[dict(name=COURSES[x['course_id']]['name'] if x['course_id'] in COURSES else x['course_id'],code=x['code'],issued_at=x['issued_at']) for x in certs])

@app.post('/data/performance/goal')
@auth_required
def set_weekly_goal():
 try:target=int(data().get('target'))
 except (ValueError,TypeError):return error('Informe uma meta válida.')
 if not 1<=target<=100:return error('A meta deve ser de 1 a 100 aulas por semana.')
 with db() as d:d.execute('INSERT INTO weekly_goals(user_id,target) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET target=excluded.target,updated_at=CURRENT_TIMESTAMP',(session['uid'],target))
 return jsonify(ok=True,target=target)

@app.post('/data/certificate/<cid>')
@auth_required
def issue_certificate(cid):
 if cid not in COURSES:return error('Curso não encontrado.',404)
 ids=[l['id'] for l in COURSES[cid]['lessons']]
 with db() as d:
  completed={r['lesson_id'] for r in d.execute('SELECT lesson_id FROM completions WHERE user_id=?',(session['uid'],))}
  if not all(i in completed for i in ids):return error('Conclua todas as aulas e avaliações do curso antes de emitir o certificado.')
  passed={r['module'] for r in d.execute('SELECT module FROM module_assessments WHERE user_id=? AND course_id=?',(session['uid'],cid))}
  if any(name not in passed for name,_ in module_groups(COURSES[cid])):return error('Aprove as avaliações finais de todos os módulos antes de emitir o certificado.')
  row=d.execute('SELECT code FROM certificates WHERE user_id=? AND course_id=?',(session['uid'],cid)).fetchone()
  if row:code=row['code']
  else:
   code=secrets.token_hex(12).upper()
   d.execute('INSERT INTO certificates(user_id,course_id,code) VALUES(?,?,?)',(session['uid'],cid,code))
 return jsonify(ok=True,code=code,url='/certificado/pdf/'+code,verify='/certificado/verificar/'+code)
@app.get('/data/certificates')
@auth_required
def certificates():
 with db() as d:
  rows=[dict(x) for x in d.execute('SELECT c.code,c.course_id,c.issued_at FROM certificates c WHERE c.user_id=? ORDER BY c.issued_at DESC',(session['uid'],))]
 for r in rows:
  course=COURSES.get(r['course_id'],{})
  r['course_name']=course.get('name',r['course_id'])
  r['hours']=course.get('hours',0)
 return jsonify(rows)

def certificate_record(code,owner=None):
 if len(code)>64 or not code.isalnum():return None
 with db() as d:
  sql='SELECT c.code,c.course_id,c.issued_at,u.name FROM certificates c JOIN users u ON u.id=c.user_id WHERE c.code=? AND NOT EXISTS (SELECT 1 FROM certificate_revocations cr WHERE cr.code=c.code)'
  params=[code.upper()]
  if owner is not None:sql+=' AND c.user_id=?';params.append(owner)
  return d.execute(sql,params).fetchone()

@app.get('/data/verify/<code>')
def verify(code):
 r=certificate_record(code)
 if not r:return error('Certificado não encontrado.',404)
 course=COURSES.get(r['course_id'],{})
 # Nome, e-mail e dados da conta não são divulgados na consulta pública.
 return jsonify(code=r['code'],course=course.get('name',r['course_id']),hours=course.get('hours',0),issued_at=r['issued_at'][:10],valid=True)

@app.get('/certificado/pdf/<code>')
@auth_required
def pdf_certificate(code):
 r=certificate_record(code,session['uid'])
 if not r:return error('Certificado não encontrado para sua conta.',404)
 course=COURSES.get(r['course_id'],{})
 title=course.get('name',r['course_id'])
 hours=course.get('hours',0)
 date=datetime.strptime(r['issued_at'][:10],'%Y-%m-%d').strftime('%d/%m/%Y')
 verify_url=url_for('verify_page',code=r['code'],_external=True)
 stream=BytesIO()
 from reportlab.pdfgen import canvas
 from reportlab.lib.utils import simpleSplit
 W,H=landscape(A4)
 c=canvas.Canvas(stream,pagesize=(W,H))
 purple=colors.HexColor('#6F3ACB');dark=colors.HexColor('#25213B');muted=colors.HexColor('#625B78')
 c.setFillColor(colors.HexColor('#FBF9FF'));c.rect(0,0,W,H,fill=1,stroke=0)
 c.setStrokeColor(purple);c.setLineWidth(5);c.roundRect(26,26,W-52,H-52,16,fill=0,stroke=1)
 c.setStrokeColor(colors.HexColor('#D8C8F7'));c.setLineWidth(1.2);c.roundRect(39,39,W-78,H-78,12,fill=0,stroke=1)
 c.setFillColor(purple);c.setFont('Helvetica-Bold',23);c.drawCentredString(W/2,H-99,'CONECTAS ELAS')
 c.setFillColor(dark);c.setFont('Helvetica-Bold',27);c.drawCentredString(W/2,H-155,'CERTIFICADO DE CONCLUSÃO')
 c.setFillColor(muted);c.setFont('Helvetica',13);c.drawCentredString(W/2,H-192,'Certificamos que')
 def centered_lines(value,font,size,y,max_width,line_height):
  c.setFont(font,size)
  for line in simpleSplit(str(value),font,size,max_width):
   c.drawCentredString(W/2,y,line);y-=line_height
  return y
 c.setFillColor(purple)
 y=centered_lines(r['name'],'Helvetica-Bold',24,H-229,W-125,30)
 c.setFillColor(muted);c.setFont('Helvetica',13);c.drawCentredString(W/2,y-12,'concluiu as aulas e avaliações do curso')
 c.setFillColor(dark)
 y=centered_lines(title,'Helvetica-Bold',22,y-51,W-130,28)
 c.setFillColor(muted);c.setFont('Helvetica',12)
 c.drawCentredString(W/2,y-22,f'Carga horária estimada: {hours} horas   |   Conclusão: {date}')
 c.setFillColor(dark);c.setFont('Helvetica-Bold',10)
 c.drawCentredString(W/2,116,'Código de autenticação: '+r['code'])
 c.setFillColor(purple);c.setFont('Helvetica',9)
 for i,line in enumerate(simpleSplit('Verifique em: '+verify_url,'Helvetica',9,W-130)):
  c.drawCentredString(W/2,98-i*12,line)
 c.setFillColor(muted);c.setFont('Helvetica',8)
 c.drawCentredString(W/2,59,'Certificado de plataforma educacional independente; não equivale a diploma oficial do SENAC ou MEC.')
 c.setTitle('Certificado - '+title);c.save();stream.seek(0)
 return send_file(stream,mimetype='application/pdf',as_attachment=request.args.get('imprimir')!='1',download_name='certificado-conectas-elas-'+r['code']+'.pdf')
@app.get('/oportunidade/<int:jid>')
def job_detail(jid):
 with db() as d:
  if not d.execute('SELECT id FROM jobs WHERE id=?',(jid,)).fetchone():return 'Oportunidade não encontrada',404
 return render_template('page.html',page='jobdetail',job_id=jid)

@app.get('/data/portfolio')
@auth_required
def portfolio_list():
 with db() as d:return jsonify([dict(r) for r in d.execute('SELECT * FROM portfolio_items WHERE user_id=? ORDER BY id DESC',(session['uid'],))])

@app.post('/data/portfolio')
@auth_required
def portfolio_create():
 x=data();title=str(x.get('title','')).strip();description=str(x.get('description','')).strip();tech=str(x.get('technologies','')).strip();url=str(x.get('project_url','')).strip();cid=str(x.get('course_id','')).strip()
 if not (2<=len(title)<=100 and 10<=len(description)<=1200 and len(tech)<=200 and len(url)<=300):return error('Confira o título, a descrição e os limites dos campos.')
 if url and not (url.startswith('https://') or url.startswith('http://')):return error('O link precisa começar com https:// ou http://.')
 if cid and cid not in COURSES:return error('Curso inválido.')
 with db() as d:
  d.execute('INSERT INTO portfolio_items(user_id,title,description,technologies,project_url,course_id) VALUES(?,?,?,?,?,?)',(session['uid'],title,description,tech,url,cid))
 return jsonify(ok=True),201

@app.delete('/data/portfolio/<int:pid>')
@auth_required
def portfolio_delete(pid):
 with db() as d:r=d.execute('DELETE FROM portfolio_items WHERE id=? AND user_id=?',(pid,session['uid']))
 if not r.rowcount:return error('Projeto não encontrado.',404)
 return jsonify(ok=True)

@app.get('/data/jobs')
def jobs():
 with db() as d:return jsonify([dict(r) | {'location':'Não informada','area':('Desenvolvimento Web' if 'Front-end' in r['title'] else 'Tecnologia'),'source_type':'demonstrativa','source_url':None} for r in d.execute('SELECT j.*,CASE WHEN s.job_id IS NULL THEN 0 ELSE 1 END saved FROM jobs j LEFT JOIN saved_jobs s ON s.job_id=j.id AND s.user_id=?',(session.get('uid',-1),))])
@app.post('/data/jobs/<int:jid>/save')
@auth_required
def save_job(jid):
 with db() as d:
  if not d.execute('SELECT 1 FROM jobs WHERE id=?',(jid,)).fetchone():return error('Vaga não encontrada.',404)
  exists=d.execute('SELECT 1 FROM saved_jobs WHERE user_id=? AND job_id=?',(session['uid'],jid)).fetchone()
  if exists:d.execute('DELETE FROM saved_jobs WHERE user_id=? AND job_id=?',(session['uid'],jid))
  else:d.execute('INSERT INTO saved_jobs VALUES(?,?)',(session['uid'],jid))
 return jsonify(saved=not bool(exists))
COMMUNITY_TOPICS=('Geral','HTML/CSS','JavaScript','Python','Java','SQL','Flask','React','Git/GitHub','UI/UX','Acessibilidade','APIs','Segurança Web')
COMMUNITY_KINDS=('discussao','projeto','conquista')
def is_moderator(c):
 return bool(session.get('uid') and (c.execute('SELECT 1 FROM community_moderators WHERE user_id=?',(session['uid'],)).fetchone() or c.execute('SELECT 1 FROM admins WHERE user_id=?',(session['uid'],)).fetchone()))
def community_post(c,pid):
 return c.execute('SELECT id FROM posts WHERE id=? AND hidden=0',(pid,)).fetchone()
@app.get('/data/community/meta')
def community_meta():
 with db() as c:return jsonify(topics=COMMUNITY_TOPICS,moderator=is_moderator(c))
@app.get('/data/posts')
def posts():
 topic=request.args.get('topic','Geral')
 if topic not in COMMUNITY_TOPICS:return error('Comunidade inválida.')
 with db() as c:
  rows=c.execute("""SELECT p.id,p.body,p.topic,p.kind,p.created_at,p.user_id,u.name,
  (SELECT count(*) FROM community_likes l WHERE l.post_id=p.id) likes,
  EXISTS(SELECT 1 FROM community_likes l WHERE l.post_id=p.id AND l.user_id=?) liked
  FROM posts p JOIN users u ON u.id=p.user_id WHERE p.hidden=0 AND (?='Geral' OR p.topic=?) ORDER BY p.id DESC LIMIT 60""",(session.get('uid',-1),topic,topic)).fetchall()
  result=[]
  for row in rows:
   item=dict(row)
   item['comments']=[dict(r) for r in c.execute('SELECT cm.id,cm.body,cm.created_at,cm.user_id,u.name FROM community_comments cm JOIN users u ON u.id=cm.user_id WHERE cm.post_id=? ORDER BY cm.id ASC LIMIT 50',(row['id'],))]
   result.append(item)
 return jsonify(result)
@app.post('/data/posts')
@auth_required
def add_post():
 x=data();body=str(x.get('body','')).strip();topic=x.get('topic','Geral');kind=x.get('kind','discussao')
 if not 1<=len(body)<=1000:return error('Publicação precisa ter de 1 a 1000 caracteres.')
 if topic not in COMMUNITY_TOPICS or kind not in COMMUNITY_KINDS:return error('Categoria inválida.')
 with db() as c:c.execute('INSERT INTO posts(user_id,body,topic,kind) VALUES(?,?,?,?)',(session['uid'],body,topic,kind))
 return jsonify(ok=True)
@app.delete('/data/posts/<int:pid>')
@auth_required
def remove_post(pid):
 with db() as c:
  row=c.execute('SELECT user_id FROM posts WHERE id=?',(pid,)).fetchone()
  if not row or (row['user_id']!=session['uid'] and not is_moderator(c)):return error('Sem permissão.',403)
  c.execute('DELETE FROM community_reports WHERE post_id=? OR comment_id IN (SELECT id FROM community_comments WHERE post_id=?)',(pid,pid))
  c.execute('DELETE FROM community_likes WHERE post_id=?',(pid,))
  c.execute('DELETE FROM community_comments WHERE post_id=?',(pid,))
  c.execute('DELETE FROM posts WHERE id=?',(pid,))
 return jsonify(ok=True)
@app.post('/data/posts/<int:pid>/like')
@auth_required
def like_post(pid):
 with db() as c:
  if not community_post(c,pid):return error('Publicação indisponível.',404)
  old=c.execute('SELECT 1 FROM community_likes WHERE post_id=? AND user_id=?',(pid,session['uid'])).fetchone()
  if old:c.execute('DELETE FROM community_likes WHERE post_id=? AND user_id=?',(pid,session['uid']))
  else:c.execute('INSERT INTO community_likes(post_id,user_id) VALUES(?,?)',(pid,session['uid']))
 return jsonify(liked=not bool(old))
@app.post('/data/posts/<int:pid>/comments')
@auth_required
def add_comment(pid):
 body=str(data().get('body','')).strip()
 if not 1<=len(body)<=500:return error('Comentário precisa ter de 1 a 500 caracteres.')
 with db() as c:
  if not community_post(c,pid):return error('Publicação indisponível.',404)
  c.execute('INSERT INTO community_comments(post_id,user_id,body) VALUES(?,?,?)',(pid,session['uid'],body))
 return jsonify(ok=True)
@app.delete('/data/comments/<int:cid>')
@auth_required
def delete_comment(cid):
 with db() as c:
  row=c.execute('SELECT user_id FROM community_comments WHERE id=?',(cid,)).fetchone()
  if not row or (row['user_id']!=session['uid'] and not is_moderator(c)):return error('Sem permissão.',403)
  c.execute('DELETE FROM community_reports WHERE comment_id=?',(cid,))
  c.execute('DELETE FROM community_comments WHERE id=?',(cid,))
 return jsonify(ok=True)
@app.post('/data/community/report')
@auth_required
def report_content():
 x=data();pid=x.get('post_id');cid=x.get('comment_id');reason=str(x.get('reason','')).strip()
 if bool(pid)==bool(cid) or not 5<=len(reason)<=300:return error('Informe o conteúdo e um motivo de 5 a 300 caracteres.')
 with db() as c:
  if pid and not community_post(c,pid):return error('Publicação indisponível.',404)
  if cid and not c.execute('SELECT 1 FROM community_comments WHERE id=?',(cid,)).fetchone():return error('Comentário indisponível.',404)
  c.execute('INSERT INTO community_reports(post_id,comment_id,reporter_id,reason) VALUES(?,?,?,?)',(pid,cid,session['uid'],reason))
 return jsonify(ok=True)
@app.get('/data/community/moderation')
@auth_required
def moderation_queue():
 with db() as c:
  if not is_moderator(c):return error('Acesso restrito à moderação.',403)
  return jsonify([dict(r) for r in c.execute('SELECT id,post_id,comment_id,reason,status,created_at FROM community_reports WHERE status=? ORDER BY id DESC LIMIT 100',('pending',))])
@app.post('/data/community/moderation/<int:rid>')
@auth_required
def moderate(rid):
 action=data().get('action')
 if action not in ('dismiss','hide'):return error('Ação inválida.')
 with db() as c:
  if not is_moderator(c):return error('Acesso restrito à moderação.',403)
  r=c.execute('SELECT * FROM community_reports WHERE id=? AND status=?',(rid,'pending')).fetchone()
  if not r:return error('Denúncia não encontrada.',404)
  if action=='hide':
   if r['post_id']:c.execute('UPDATE posts SET hidden=1 WHERE id=?',(r['post_id'],))
   if r['comment_id']:c.execute('DELETE FROM community_reports WHERE comment_id=? AND id<>?',(r['comment_id'],rid));c.execute('DELETE FROM community_comments WHERE id=?',(r['comment_id'],))
  c.execute('UPDATE community_reports SET status=? WHERE id=?',('resolved' if action=='hide' else 'dismissed',rid))
 return jsonify(ok=True)
if __name__=='__main__':app.run(debug=os.getenv('FLASK_DEBUG')=='1',port=int(os.getenv('PORT',5000)))


# ETAPA 4: histórico privado por conta, sem chaves expostas ao navegador.
@app.get('/data/tutor/history')
@auth_required
def tutor_history():
 with db() as c:
  rows=c.execute('SELECT id,role,body,created_at FROM tutor_messages WHERE user_id=? ORDER BY id DESC LIMIT 40',(session['uid'],)).fetchall()
 return jsonify(messages=[dict(r) for r in reversed(rows)])

@app.delete('/data/tutor/history')
@auth_required
def tutor_clear():
 with db() as c:c.execute('DELETE FROM tutor_messages WHERE user_id=?',(session['uid'],))
 return jsonify(ok=True)

@app.post('/data/tutor/message')
@auth_required
def tutor_message():
 payload=data();question=payload.get('question','');level=payload.get('level','iniciante');mode=payload.get('mode','explain');lid=payload.get('lesson_id','')
 if not isinstance(question,str) or not 1<=len(question.strip())<=4000:return error('Escreva uma pergunta de até 4.000 caracteres.')
 if level not in ('iniciante','intermediario','avancado') or mode not in ('explain','debug','lines','hint'):return error('Preferências inválidas.')
 if not isinstance(lid,str):return error('Aula inválida.')
 context=''
 if lid and lid in LESSONS:
  course,lesson=LESSONS[lid];states,_=access_state(course['id'],session['uid'])
  if states[lesson.get('module','Módulo')]['unlocked']:
   context=f"Curso: {course['name']}; módulo: {lesson.get('module','')}; aula: {lesson['title']}; conteúdo: {lesson.get('body','')[:600]}"
 with db() as c:
  rows=c.execute('SELECT role,body FROM tutor_messages WHERE user_id=? ORDER BY id DESC LIMIT 8',(session['uid'],)).fetchall()
 history=[]
 for row in reversed(rows):
  if row['role']=='user':history.append({'q':row['body'][:2000],'text':''})
  elif history:history[-1]['text']=row['body'][:4000]
 history=[h for h in history if h['text']][-4:]
 guide={'explain':'Explique com exemplos progressivos.','debug':'Identifique erros, explique a causa e proponha uma correção.','lines':'Explique o código linha por linha.','hint':'Dê apenas dicas graduais, sem entregar a solução completa.'}[mode]
 prompt=f"Nível: {level}. Modo: {guide} Contexto da aula: {context or 'Nenhuma aula selecionada'}. Pergunta da aluna: {question.strip()}"
 from codestart_engine import ask_ai
 if os.getenv('OPENAI_API_KEY','').strip():
  response=ask_ai(prompt,history)
  if isinstance(response,tuple):return response
  result=response.get_json()
  if not result.get('success'):return response
  answer=result['answer'];source='ai'
 else:
  # Modo demonstrativo local: não apresenta a busca por conteúdo como IA generativa.
  terms=[w.lower() for w in question.split() if len(w)>3]
  selected=None;score=0
  for course in CURRICULUM['courses']:
   for lesson in course['lessons']:
    hay=(lesson.get('title','')+' '+lesson.get('body','')).lower()
    n=sum(t in hay for t in terms)
    if n>score:score=n;selected=lesson
  if selected:
   answer=f"Material relacionado: {selected['title']}\n\n{selected.get('body','')[:900]}\n\nDica: experimente um exemplo pequeno e explique o resultado com suas palavras."
  else:answer='A IA externa ainda não está configurada. Configure OPENAI_API_KEY no servidor para receber explicações personalizadas. Você pode consultar os cursos enquanto isso.'
  source='local'
 with db() as c:
  c.execute('INSERT INTO tutor_messages(user_id,role,body) VALUES(?,?,?)',(session['uid'],'user',question.strip()))
  c.execute('INSERT INTO tutor_messages(user_id,role,body) VALUES(?,?,?)',(session['uid'],'assistant',answer[:12000]))
  c.execute('DELETE FROM tutor_messages WHERE user_id=? AND id NOT IN (SELECT id FROM tutor_messages WHERE user_id=? ORDER BY id DESC LIMIT 100)',(session['uid'],session['uid']))
 return jsonify(answer=answer,mode=source)


EDITOR_LANGUAGES={'javascript','html','css','python','java','json','sql'}
@app.get('/data/editor/projects')
@auth_required
def editor_projects():
 with db() as c: rows=c.execute('SELECT id,title,language,lesson_id,updated_at FROM editor_projects WHERE user_id=? ORDER BY updated_at DESC,id DESC',(session['uid'],)).fetchall()
 return jsonify(projects=[dict(r) for r in rows])

@app.get('/data/editor/projects/<int:pid>')
@auth_required
def editor_project_get(pid):
 with db() as c:r=c.execute('SELECT * FROM editor_projects WHERE id=? AND user_id=?',(pid,session['uid'])).fetchone()
 return jsonify(project=dict(r)) if r else error('Projeto não encontrado.',404)

@app.post('/data/editor/projects')
@auth_required
def editor_project_save():
 x=data();title=str(x.get('title','')).strip();lang=str(x.get('language',''));code=x.get('code','');lid=x.get('lesson_id')
 if not 1<=len(title)<=100 or lang not in EDITOR_LANGUAGES or not isinstance(code,str) or len(code)>50000:return error('Informe título, linguagem e código válido (máximo 50 mil caracteres).')
 if lid is not None and (not isinstance(lid,str) or lid not in LESSONS):return error('Aula inválida.')
 pid=x.get('id')
 with db() as c:
  if pid is not None:
   if not isinstance(pid,int):return error('ID inválido.')
   r=c.execute('UPDATE editor_projects SET title=?,language=?,code=?,lesson_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?',(title,lang,code,lid,pid,session['uid']))
   if not r.rowcount:return error('Projeto não encontrado.',404)
  else:pid=c.execute('INSERT INTO editor_projects(user_id,title,language,code,lesson_id) VALUES(?,?,?,?,?)',(session['uid'],title,lang,code,lid)).lastrowid
 return jsonify(ok=True,id=pid)

@app.delete('/data/editor/projects/<int:pid>')
@auth_required
def editor_project_delete(pid):
 with db() as c:r=c.execute('DELETE FROM editor_projects WHERE id=? AND user_id=?',(pid,session['uid']))
 return jsonify(ok=True) if r.rowcount else error('Projeto não encontrado.',404)

@app.post('/data/editor/challenges/<challenge_id>/attempt')
@auth_required
def editor_challenge_attempt(challenge_id):
 # Resultados de execução no navegador não são confiáveis para premiações ou certificados.
 # Registrar apenas tentativa, sem creditar XP ou progresso com base em dados do cliente.
 if challenge_id not in ('js-soma','js-par','js-saudacao'):return error('Desafio inválido.',404)
 passed=data().get('passed') is True
 with db() as c:c.execute('INSERT INTO editor_challenge_attempts(user_id,challenge_id,passed) VALUES(?,?,?)',(session['uid'],challenge_id,int(passed)))
 return jsonify(ok=True,recorded=True)


# ETAPA 10: permissões persistentes, nunca confiar em papéis enviados pelo navegador.
def admin_required(fn):
 @wraps(fn)
 def wrapper(*args,**kwargs):
  if not session.get('uid'):return error('Entre na sua conta.',401)
  with db() as d:
   if not d.execute('SELECT 1 FROM admins WHERE user_id=?',(session['uid'],)).fetchone():return error('Acesso exclusivo para administradores autorizados.',403)
  return fn(*args,**kwargs)
 return wrapper

def audit(d,action,entity):
 d.execute('INSERT INTO admin_audit(admin_id,action,entity) VALUES(?,?,?)',(session['uid'],action,str(entity)[:120]))

@app.get('/data/admin/access')
@admin_required
def admin_access():return jsonify(ok=True)

@app.get('/data/admin/overview')
@admin_required
def admin_overview():
 with db() as d:
  count=lambda sql:d.execute(sql).fetchone()[0]
  users=count('SELECT COUNT(*) FROM users'); started=count('SELECT COUNT(DISTINCT user_id) FROM completions')
  completed=count('SELECT COUNT(*) FROM certificates')
  views=[dict(r) for r in d.execute('SELECT course_id,COUNT(*) views FROM course_views GROUP BY course_id ORDER BY views DESC LIMIT 10')]
  issues=[dict(r) for r in d.execute('SELECT lesson_id,COUNT(*) errors FROM quiz_attempts WHERE correct=0 GROUP BY lesson_id ORDER BY errors DESC LIMIT 10')]
  return jsonify(users=users,active_students=started,certificates=completed,completion_rate=round(100*completed/max(1,users*len(COURSES)),1),courses=len(COURSES),posts=count('SELECT COUNT(*) FROM posts'),reports=count("SELECT COUNT(*) FROM community_reports WHERE status='pending'"),views=[dict(name=COURSES.get(x['course_id'],{}).get('name',x['course_id']),**x) for x in views],difficulties=issues)

@app.get('/data/admin/courses')
@admin_required
def admin_courses():
 return jsonify([dict(id=c['id'],name=c['name'],description=c.get('description',''),category=c.get('category','Geral'),level=c.get('level','Iniciante'),hours=c.get('hours',0),modules=sorted({l.get('module','Geral') for l in c['lessons']}),lessons=c['lessons']) for c in COURSES.values()])

@app.post('/data/admin/courses')
@admin_required
def admin_save_course():
 x=data();cid=str(x.get('id','')).strip().lower();name=str(x.get('name','')).strip()
 if not cid or len(cid)>60 or not all(ch.isalnum() or ch=='-' for ch in cid) or not 3<=len(name)<=100:return error('ID (letras, números ou hífen) e nome válido são obrigatórios.')
 old=COURSES.get(cid,{});course=dict(old)
 course.update(id=cid,name=name,description=str(x.get('description',''))[:1500],category=str(x.get('category','Geral'))[:80],level=str(x.get('level','Iniciante'))[:50],hours=max(0,min(999,int(x.get('hours',0) or 0))))
 course.setdefault('lessons',[])
 with db() as d:
  d.execute('INSERT INTO admin_course_data(course_id,payload) VALUES(?,?) ON CONFLICT(course_id) DO UPDATE SET payload=excluded.payload,updated_at=CURRENT_TIMESTAMP',(cid,json.dumps(course,ensure_ascii=False)))
  audit(d,'salvar curso',cid)
 COURSES[cid]=course;load_admin_courses()
 return jsonify(ok=True,id=cid)

@app.post('/data/admin/courses/<cid>/lessons')
@admin_required
def admin_save_lesson(cid):
 if cid not in COURSES:return error('Curso não encontrado.',404)
 x=data();lid=str(x.get('id','')).strip();title=str(x.get('title','')).strip();module=str(x.get('module','')).strip()
 if not 3<=len(title)<=120 or not 2<=len(module)<=100:return error('Informe título e módulo válidos.')
 if not lid:lid=cid+'-admin-'+secrets.token_hex(5)
 if lid in LESSONS and LESSONS[lid][0]['id']!=cid:return error('ID de aula já usado por outro curso.')
 course=json.loads(json.dumps(COURSES[cid]));lessons=course['lessons'];existing=next((i for i,l in enumerate(lessons) if l['id']==lid),None)
 lesson=lessons[existing].copy() if existing is not None else {}
 lesson.update(id=lid,title=title,module=module,body=str(x.get('body',''))[:12000],objectives=x.get('objectives',[]) if isinstance(x.get('objectives'),list) else [],theory=x.get('theory',[]) if isinstance(x.get('theory'),list) else [],practice=str(x.get('practice',''))[:5000],challenge=str(x.get('challenge',''))[:5000],question=str(x.get('question',''))[:1500],options=x.get('options',[]) if isinstance(x.get('options'),list) else [],answer=int(x.get('answer',0) or 0),explanation=str(x.get('explanation',''))[:3000])
 if len(lesson['options'])<2 or len(lesson['options'])>6 or not 0<=lesson['answer']<len(lesson['options']):return error('Avaliação: informe de 2 a 6 alternativas e índice correto.')
 if existing is None:lessons.append(lesson)
 else:lessons[existing]=lesson
 with db() as d:
  d.execute('INSERT INTO admin_course_data(course_id,payload) VALUES(?,?) ON CONFLICT(course_id) DO UPDATE SET payload=excluded.payload,updated_at=CURRENT_TIMESTAMP',(cid,json.dumps(course,ensure_ascii=False)))
  audit(d,'salvar aula',lid)
 COURSES[cid]=course;load_admin_courses()
 return jsonify(ok=True,id=lid)

@app.get('/data/admin/jobs')
@admin_required
def admin_jobs():
 with db() as d:return jsonify([dict(r) for r in d.execute('SELECT * FROM jobs ORDER BY id DESC')])

@app.post('/data/admin/jobs')
@admin_required
def admin_save_job():
 x=data();title=str(x.get('title','')).strip();org=str(x.get('organization','')).strip()
 if not 3<=len(title)<=120 or not 2<=len(org)<=120:return error('Título e organização obrigatórios.')
 with db() as d:
  jid=int(x.get('id') or 0);fields=(title,org,str(x.get('mode','Remoto'))[:50],str(x.get('category','Projeto'))[:50],str(x.get('description',''))[:3000])
  if jid:
   r=d.execute('UPDATE jobs SET title=?,organization=?,mode=?,category=?,description=? WHERE id=?',(*fields,jid))
   if not r.rowcount:return error('Oportunidade não encontrada.',404)
  else:jid=d.execute('INSERT INTO jobs(title,organization,mode,category,description) VALUES(?,?,?,?,?)',fields).lastrowid
  audit(d,'salvar oportunidade',jid)
 return jsonify(ok=True,id=jid)

@app.get('/data/admin/certificates')
@admin_required
def admin_certificates():
 with db() as d:return jsonify([dict(r) for r in d.execute('SELECT c.code,c.course_id,c.issued_at, u.name,CASE WHEN r.code IS NULL THEN 0 ELSE 1 END revoked FROM certificates c JOIN users u ON u.id=c.user_id LEFT JOIN certificate_revocations r ON r.code=c.code ORDER BY c.id DESC LIMIT 150')])

@app.post('/data/admin/certificates/<code>/revoke')
@admin_required
def admin_revoke_certificate(code):
 reason=str(data().get('reason','')).strip()
 if not 5<=len(reason)<=300:return error('Informe um motivo de 5 a 300 caracteres.')
 with db() as d:
  if not d.execute('SELECT 1 FROM certificates WHERE code=?',(code,)).fetchone():return error('Certificado não encontrado.',404)
  d.execute('INSERT OR REPLACE INTO certificate_revocations(code,reason) VALUES(?,?)',(code,reason));audit(d,'revogar certificado',code)
 return jsonify(ok=True)
