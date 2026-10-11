import json, datetime, re
from decimal import Decimal
ONES=['sıfır','bir','iki','üç','dört','beş','altı','yedi','sekiz','dokuz']
TENS=['','on','yirmi','otuz','kırk','elli','altmış','yetmiş','seksen','doksan']
MONTHS=['','Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']
ORD=['','birinci','ikinci','üçüncü','dördüncü']
CURRENCIES=[('TL','Türk Lirası'),('USD','Dolar'),('EUR','Euro'),('GBP','İngiliz Sterlini')]
def words(n):
 n=int(n)
 if n<0:return 'eksi '+words(-n)
 if n<10:return ONES[n]
 if n<100:return TENS[n//10]+(' '+ONES[n%10] if n%10 else '')
 if n<1000:return (ONES[n//100]+' ' if n//100>1 else '')+'yüz'+(' '+words(n%100) if n%100 else '')
 for size,label in [(10**9,'milyar'),(10**6,'milyon'),(1000,'bin')]:
  if n>=size:return ('' if size==1000 and n//size==1 else words(n//size)+' ')+label+(' '+words(n%size) if n%size else '')
def money(n,c):
 d=Decimal(str(n)); whole=int(abs(d)); frac=int((abs(d)-whole)*100)
 unit=dict(CURRENCIES)[c] if not frac or c!='TL' else 'lira'
 return words(whole)+' '+unit+(' '+words(frac)+' '+('kuruş' if c=='TL' else 'peni' if c=='GBP' else 'sent') if frac else '')
def date(v):
 try:
  d,m,y=map(int,str(v).split('.'));return str(d)+' '+MONTHS[m]+' '+str(y)
 except:return ''
def dt(v):
 try:return datetime.datetime.strptime(str(v),'%d.%m.%Y').date()
 except:return None
def digits(v):return ' '.join(ONES[int(x)] for x in str(v) if x.isdigit())
def safe(v):
 s=str(v or '')
 if any(x in s.lower() for x in ['talimat','ignore','instruction','numarasını oku','system','sistem istem','pretend']):return ''
 return s
def obj(v):
 try:return json.loads(v) if isinstance(v,str) else v or {}
 except:return {}
def cardintro(v):return 'Sonu '+digits(v.get('cardNumberLast4',''))+' ile biten '+(safe(v.get('productName'))+' ' if safe(v.get('productName')) else '')+'kartınız'
def joinnames(a):return a[0] if len(a)==1 else ', '.join(a[:-1])+' ve '+a[-1] if a else ''
def reading(v,b):
 today=datetime.datetime.fromisoformat(str(v.get('now',''))).date()
 issued=dt(b.get('statementDate'));due=dt(b.get('lastPayDate'));nxt=dt(b.get('nextStatementDate'))
 intro=cardintro(obj(v.get('selected_json')))
 nod=b.get('statementPaymentStatus')=='NO_DEBT'
 v['no_statement']='yes' if nod or not issued else 'no'
 due_line=('Borçlarınız için son ödeme tarihiniz bugündür.' if due==today else "Borçlarınız için son ödeme tarihiniz "+date(b.get('lastPayDate'))+"'dir.") if due else ''
 v['due_line']=due_line
 if not issued:
  return intro+'. Kartınızın henüz kesilmiş bir ekstresi olmadığı için ekstre borcunuz bulunmamaktadır.'+(' İlk hesap kesim tarihiniz '+date(b.get('nextStatementDate'))+' olacak.' if nxt else '')
 cut=today==issued or today==nxt
 late=due and today>due
 if nod and not cut:
  s=intro+'ın '+date(b.get('statementDate'))+' tarihli ekstresinden borcunuz bulunmamaktadır.'
  if 'totalDebt' in (b.get('debtTL') or {}):
   total=b['debtTL']['totalDebt'];s+=(' Gelecek dönemler dahil toplam borcunuz '+money(total,'TL')+"'dir." if total>0 else ' Türk Lirası borcunuz bulunmamaktadır.')
  return s+(' Son ödeme tarihiniz '+date(b.get('lastPayDate'))+' olacaktır.' if due else '')
 lines=[];clear=[]
 for c,name in CURRENCIES:
  d=b.get('debt'+c)
  if not d:continue
  key='totalDebt' if cut or late else 'remainingDebt'
  if key not in d:continue
  if d[key]<=0:clear.append(name);continue
  if cut or late:s=name+' toplam borcunuz '+money(d['totalDebt'],c)+"'dir."
  elif c=='TL':
   debt=money(d['statementDebt'],c);minimum=money(d['minPayment'],c);remaining=money(d['remainingDebt'],c);remmin=d['remainingMinPayment']
   if remmin<=0:s='Türk Lirası borcunuz '+debt+', kalan toplam borcunuz '+remaining+"'dir. Minimum ödemenizi yaptığınız için teşekkür ederiz."
   elif remmin>=d['minPayment']:s='Türk Lirası borcunuz '+debt+', ödenmesi gereken minimum tutar '+minimum+"'dir."
   else:s='Türk Lirası borcunuz '+debt+', ödenmesi gereken minimum tutar '+minimum+', kalan toplam borcunuz '+remaining+', kalan minimum ödeme tutarınız '+money(remmin,c)+"'dir."
  else:s=name+' borcunuz '+money(d['statementDebt'],c)+', kalan toplam borcunuz '+money(d['remainingDebt'],c)+', ödenmesi gereken minimum tutar '+money(d['minPayment'],c)+"'dir."
  lines.append(s)
 opening=intro+'a ait '+date(b.get('statementDate'))+' tarihinde kesilen ekstre '
 if cut:opening=intro+'. Hesap kesim tarihiniz bugün, ekstreniz saat 00.00 itibarıyla kesilecek. '
 elif late:opening=intro+'. Son ödeme tarihiniz geçmiştir. '
 transfer=[name for c,name in CURRENCIES[1:] if (b.get('debt'+c) or {}).get('transferAmount',0)>0]
 if transfer:opening+=joinnames(transfer)+' borcunuz Türk Lirasına aktarılmıştır. '
 if clear:lines.append(next((x['text'] for x in globals().get('SOURCE_TEMPLATES',[]) if x['text']==joinnames(clear)+' borcunuz bulunmamaktadır.'),joinnames(clear)+' borcunuz bulunmamaktadır.'))
 a=(b.get('debtTL') or {}).get('remainAutomaticPaymentAmount',0)
 if late and b.get('automaticPaymentFlag')=='Y' and a>0:lines.append('Otomatik ödemenizden kalan tutar '+money(a,'TL')+"'dir.")
 lines.append(due_line)
 if v.get('figure')=='due':return due_line
 if v.get('figure')=='minimum':return intro+'. '+ ' '.join(name+' minimum ödeme tutarınız '+money(b['debt'+c]['minPayment'],c)+'.' for c,name in CURRENCIES if b.get('debt'+c) and 'minPayment' in b['debt'+c])
 return opening+' '.join(lines)
def main(v,event):
 v['route']='fin_error'
 def go(t,line=None):
  v['route']=t
  if line is not None:v['say_next']=line;v['last_line']=line
 def tries(stage,line):
  k='tries_'+stage;v[k]=str(int(v.get(k,0))+1)
  if int(v[k])>=3:go('fin_tries')
  else:go(stage,line)
 def offer():
  if v.get('no_statement')=='yes':go('fin_menu');return
  e=bool(v.get('email')); used=v.get('change_used')==str(datetime.datetime.fromisoformat(v['now']).year)
  line=('Hesap kesim tarihinizi değiştirebilirim ya da ekstrenizi kayıtlı mail adresinize gönderebilirim.' if e and not used else 'Hesap kesim tarihinizi değiştirebilirim.' if not used else 'Ekstrenizi kayıtlı mail adresinize gönderebilirim.' if e else '')
  go('offer',line) if line else go('fin_menu')
 def email():
  if not v.get('email'):go('offer','Bankamızda kayıtlı bir e-posta adresiniz bulunmadığı için ekstrenizi gönderemiyorum. Hesap kesim tarihinizi değiştirebilirim.');return
  if not v.get('statement_date'):go('fin_error');return
  go('email_confirm','Ekstrenizi '+v['email_speech']+' adresine göndermemi ister misiniz?')
 def choose():
  cards=obj(v.get('cards_json')); cards=cards if isinstance(cards,list) else []
  name=str(v.get('card_name','')).strip().lower();num=str(v.get('card_digits','')).strip()
  pool=obj(v.get('candidates_json'));pool=pool if isinstance(pool,list) and pool else cards
  found=[]
  if num:
   if len(num)==4:found=[c for c in pool if str(c.get('cardNumberLast4'))==num]
   elif len(num)==6:
    found=[c for c in pool if '*' not in str(c.get('cardNumber')) and str(c.get('cardNumber'))[-6:]==num]
    if not found and any('*' in str(c.get('cardNumber')) for c in pool):go('select','Son altı hanesi aynı olan birden fazla kartınız var. Kart numaranızı söyler misiniz?');v['digit_stage']='full';return
   elif len(num)>=12:found=[c for c in cards if str(c.get('cardNumber'))==num or ('*' in str(c.get('cardNumber')) and len(str(c.get('cardNumber')))==len(num) and all(a=='*' or a==b for a,b in zip(str(c.get('cardNumber')),num)))]
  elif name:found=[c for c in cards if name in safe(c.get('productName')).lower()]
  generic={'kredi kartı','kredi kartım','kartım','kart','borç','borcum','borcumu','ekstre','ekstre borcu'}
  if len(cards)==1 and not num and (not name or name in generic) and v.get('topic')!='all':found=cards
  if len(found)==1:
   c=found[0]
   if str(c.get('isMainCard')).lower()=='false':tries('select','Bu kartınız için uygun bir ekstre bulunmuyor. Lütfen başka bir kartınızı seçin.');return
   v['selected_json']=json.dumps(c,ensure_ascii=False);v['card_id']=c['cardNumber'];v['candidates_json']='[]';v['tries_select']='0';go('api_balance');return
  if len(found)>1:
   v['candidates_json']=json.dumps(found,ensure_ascii=False)
   if num and len(num)==4:go('select','Son dört hanesi '+digits(num)+' olan birden fazla kartınız var. Kartınızın son altı hanesini söyler misiniz?');v['digit_stage']='six'
   elif num:go('select','Son altı hanesi aynı olan birden fazla kartınız var. Kart numaranızı söyler misiniz?');v['digit_stage']='full'
   else:go('select',safe(found[0].get('productName'))+' isimli birden fazla kartınız var. Kartınızın son dört hanesini söyler misiniz?');v['digit_stage']='four'
  else:
   examples=list(dict.fromkeys(safe(c.get('productName')) or 'sonu '+digits(c.get('cardNumberLast4'))+' ile biten kart' for c in cards))
   line='Hangi kartınızın borcunu öğrenmek istersiniz?'+(' Örneğin, '+' veya '.join(examples[:2])+' diyebilirsiniz.' if examples else '')
   if name or num or v.get('topic')=='all':tries('select',('Bu isimde uygun bir kartınız bulunmuyor. '+ 'Kartlarınız: '+', '.join(examples)+'. ' if name else '')+line)
   else:go('select',line)
 topic=v.get('topic','none');confirm=v.get('confirm','unclear')
 if event.startswith('turn_'):
  stage=event[5:]
  if topic=='human':go('fin_human')
  elif topic=='payment' and stage in ('opening','clarify_payment') and v.get('payment_intent')!='explicit':
   go('clarify_payment','Ekstre borcunuzu öğrenmek mi istiyorsunuz, yoksa borç ödeme işlemi mi yapmak istiyorsunuz?')
  elif topic=='payment':go('fin_payment')
  elif topic=='dispute':go('fin_dispute')
  elif topic=='third_party':go('fin_login')
  elif topic=='foreign':go('fin_foreign')
  elif topic in ['done','stop']:go('fin_menu')
  elif topic=='silence':
   v['silence_count']=str(int(v.get('silence_count',0))+1)
   if int(v['silence_count'])>=3:go('fin_silence')
   else:go(stage,v.get('last_line','Hangi kartınızın borcunu öğrenmek istersiniz?'))
  elif topic=='repeat':go(stage,v.get('last_line',''))
  elif topic=='angry':
   v['angry_count']=str(int(v.get('angry_count',0))+1)
   if int(v['angry_count'])>3:go('fin_human')
   else:go(stage,'Size yardımcı olmak için buradayım. '+v.get('last_line',''))
  elif topic=='out_scope' and stage!='outside':v['resume']=stage;v['resume_line']=v.get('last_line','');go('outside','Size bu konuda yardımcı olamıyorum. Sizi ana menüye aktarmamı ister misiniz?')
  elif topic=='secret':go(stage,'Güvenliğiniz için şifrelerinizi paylaşmayın; şifre istemiyoruz. '+v.get('last_line',''))
  elif topic=='raw':go(stage,'Yalnızca kartınızın son dört hanesini ve ekstre bilgilerinizi paylaşabilirim. '+v.get('last_line',''))
  elif stage=='outside':
   if confirm=='yes':go('fin_menu')
   elif confirm=='no':go(v.get('resume','select'),v.get('resume_line','Hangi kartınızın borcunu öğrenmek istersiniz?'))
   else:tries(stage,'Size bu konuda yardımcı olamıyorum. Sizi ana menüye aktarmamı ister misiniz?')
  elif stage in ('opening','clarify_payment'):
   v['initial_name']=v.get('card_name','');v['initial_digits']=v.get('card_digits','');v['initial_all']='yes' if topic=='all' else 'no'
   v['pending']= 'email' if topic in ['email','old_statement'] else 'week' if topic=='week' else ''
   go('api_list')
  elif stage=='select':
   if not v.get('card_name') and not v.get('card_digits') and topic!='all':tries(stage,v.get('last_line','Hangi kartınızın borcunu öğrenmek istersiniz?'))
   else:choose()
  elif stage in ['reading','another','offer','completed']:
   if stage=='completed' and topic=='undo':go('completed','Değişiklik zaten gerçekleşti. Yeni hesap kesim tarihiniz '+date(v.get('preview_date'))+'.')
   elif topic=='switch' or (stage=='another' and confirm=='yes'):v['card_name']=v.get('card_name','');v['candidates_json']='[]';choose()
   elif topic in ['email','old_statement','other_address','resend']:
    if int(v.get('send_count',0))>=3:go('fin_menu')
    elif topic=='old_statement':go('latest','Yalnızca son kesilmiş ekstrenizi gönderebilirim. Son ekstrenizi ister misiniz?')
    elif topic=='other_address':go('latest','Yalnızca bankamızda kayıtlı e-posta adresinize gönderebilirim. Kayıtlı adresinize göndermemi ister misiniz?')
    else:email()
   elif topic=='week':
    if v.get('change_used')==str(datetime.datetime.fromisoformat(v['now']).year):go('offer','Hesap kesim tarihinizi yılda bir kez değiştirebilirsiniz.')
    else:go('api_week')
   elif stage=='reading':
    seen=obj(v.get('seen_json'));seen=seen if isinstance(seen,list) else []
    if len(seen)<len(obj(v.get('cards_json'))):go('another','Başka bir kartınızın borcunu öğrenmek ister misiniz?')
    elif v.get('pending')=='email':email()
    elif v.get('pending')=='week':go('api_week')
    else:offer()
   elif stage=='another' and confirm=='no':offer()
   elif stage=='completed':go('fin_menu')
   else:tries(stage,v.get('last_line',''))
  elif stage=='latest':
   if confirm=='yes':email()
   elif confirm=='no':go('fin_menu')
   else:tries(stage,v.get('last_line',''))
  elif stage=='email_confirm':
   if topic=='other_address':go('latest','Yalnızca kayıtlı adresinize gönderebilirim. Kayıtlı adresinize göndermemi ister misiniz?')
   elif topic=='old_statement':go('latest','Yalnızca son kesilmiş ekstrenizi gönderebilirim. Son ekstrenizi ister misiniz?')
   elif topic=='obsolete':go('fin_obsolete')
   elif confirm=='yes':v['email_agreed']='yes';go('currency' if not v.get('currency') else 'api_send','Ekstrenizi hangi para biriminde istersiniz: Türk Lirası, Dolar, Euro veya İngiliz Sterlini?')
   elif confirm=='no':go('fin_menu')
   else:tries(stage,'Ekstrenizi '+v['email_speech']+' adresine göndermemi ister misiniz?')
  elif stage=='currency':
   if v.get('currency') in ['TL','USD','EUR','GBP']:go('api_send')
   else:tries(stage,'Ekstrenizi hangi para biriminde istersiniz: Türk Lirası, Dolar, Euro veya İngiliz Sterlini?')
  elif stage=='week_current':
   if v.get('week_choice') in ['1','2','3','4'] and str(v['week_choice'])!=str(v.get('current_week')):v['new_week']=v['week_choice'];go('api_preview')
   elif confirm=='yes':go('week_choice',v.get('week_options',''))
   elif topic=='week' and confirm=='no':tries(stage,v.get('last_line',''))
   elif confirm=='no':go('fin_menu')
   else:tries(stage,v.get('last_line',''))
  elif stage in ['week_choice','week_confirm']:
   w=str(v.get('week_choice',''))
   if stage=='week_confirm' and confirm=='yes' and not w:v['week_agreed']='yes';go('api_change')
   elif w in ['1','2','3','4']:
    if w==str(v.get('current_week')):go('fin_same')
    else:v['new_week']=w;v['week_agreed']='no';go('api_preview')
   elif topic=='week' and confirm=='no':tries(stage,v.get('last_line',''))
   elif confirm=='no':go('fin_menu')
   else:tries(stage,v.get('last_line',''))
  else:tries(stage,v.get('last_line',''))
  v['previous_line']=v.get('say_next','')
  for k in ['card_name','card_digits','week_choice']:v[k]=''
  v['topic']='none';v['confirm']='unclear'
 elif event=='list':
  v['card_name']=v.get('initial_name','');v['card_digits']=v.get('initial_digits','');v['topic']='all' if v.get('initial_all')=='yes' else ''
  if not obj(v.get('cards_json')):go('fin_no_card')
  else:choose()
  v['card_name']='';v['card_digits']='';v['topic']=''
 elif event=='balance':
  b=obj(v.get('balance_json'));v['statement_date']=b.get('statementDate','');v['currency']='';v['read_line']=reading(v,b)
  seen=obj(v.get('seen_json'));seen=seen if isinstance(seen,list) else []
  if v.get('card_id') not in seen:seen.append(v['card_id'])
  v['seen_json']=json.dumps(seen);go('api_contact')
 elif event=='contact':
  d=obj(v.get('contact_json'));v['email']=d.get('ibanEmail','') if d.get('communicationType')!='Phone' else ''
  e=v['email'];local=e.split('@')[0];domain=e.split('@')[-1]
  v['email_speech']=(local[:1]+' ile başlayan '+domain+' adresiniz') if len(local)>18 or sum(x in local for x in '.-_')>2 else d.get('ttsEmail') or e
  read=v.get('read_line','')
  seen=obj(v.get('seen_json'));cards=obj(v.get('cards_json'))
  if v.get('pending')=='email':
   email();v['pending']=''
  elif len(seen)<len([c for c in cards if str(c.get('isMainCard')).lower()!='false']):go('another','Başka bir kartınızın borcunu öğrenmek ister misiniz?')
  else:offer()
  if v.get('route')=='fin_menu':go('completed',read+' Sizi ana menüye yönlendiriyorum.')
  else:v['say_next']=read+' '+v.get('say_next','');v['last_line']=v['say_next']
 elif event=='week':
  d=obj(v.get('week_json'));v['current_week']=str(d.get('statementWeek',''));v['current_day']=str(d.get('statementDay',''));w=int(d['statementWeek']);v['relation']=d.get('relationType','');v['related_name']=safe(d.get('relatedCardProductName'))
  opts=[ORD[x] for x in range(1,5) if x!=w];v['week_options']='Hesap kesim tarihinizi ayın '+', '.join(opts[:-1])+' ya da '+opts[-1]+' haftasına alabilirim. Hangisini tercih edersiniz?'
  line=cardintro(obj(v.get('selected_json')))+'ın hesap kesim tarihi her ayın '+ORD[w]+' haftası olarak tanımlı. '
  if v['relation'] in ['M','C']:line+=cardintro({'cardNumberLast4':str(d.get('relatedCardNumber',''))[-4:],'productName':v['related_name']})+'ın hesap kesim tarihi de her ayın '+ORD[w]+' haftası olarak tanımlı. '
  line+='Bir sonraki hesap kesim tarihiniz '+date(d.get('nextStatementDate'))+', son ödeme tarihiniz '+date(d.get('nextLastPayDate'))+'. Hesap kesim tarihinizi değiştirmek ister misiniz?'
  go('week_current',line)
 elif event=='preview':
  d=obj(v.get('preview_json'));v['preview_date']=d.get('statementDate','');v['preview_due']=d.get('statementDueDate','');v['week_agreed']='no'
  line='Yeni hesap kesim haftanız her ayın '+ORD[int(v['new_week'])]+' haftası olacak. Yeni hesap kesim tarihiniz '+date(v['preview_date'])+', son ödeme tarihiniz '+date(v['preview_due'])+' olacak. '
  if v.get('relation')=='M':line+='Bu değişiklik kartınıza bağlı '+v['related_name']+' kartınızı da etkileyecek. '
  elif v.get('relation')=='C':line+='Bu değişiklik kartınızın bağlı olduğu '+v['related_name']+' kartınızı da etkileyecek. '
  go('week_confirm',line+'Onaylıyor musunuz?')
 elif event=='change':
  v['change_used']=str(datetime.datetime.fromisoformat(v['now']).year)
  go('completed',cardintro(obj(v.get('selected_json')))+'ın hesap kesim haftası her ayın '+ORD[int(v['new_week'])]+' haftası olarak değiştirildi. Yeni hesap kesim tarihiniz '+date(v.get('preview_date'))+', son ödeme tarihiniz '+date(v.get('preview_due'))+'. Sizi ana menüye yönlendiriyorum.')
 elif event=='send':
  v['send_count']=str(int(v.get('send_count',0))+1);v['email_agreed']='no';go('completed','Ekstreniz kayıtlı e-posta adresinize gönderildi. Sizi ana menüye yönlendiriyorum.')
