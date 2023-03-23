from flask import Flask,render_template,request,flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager,UserMixin,login_user,current_user,logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField,SubmitField,BooleanField
from wtforms.validators import DataRequired,Length,Email,EqualTo,ValidationError
from itsdangerous import TimedJSONWebSignatureSerializer as ser
from flask_mail import Mail,Message
import os

import  alphaToBraille
import textwrap
import fitz
from flask import send_file

from gtts import gTTS


from fpdf import FPDF


# these are helper functions
def send_reset_email(user):
    token=user.get_reset_token()
    msg=Message('BrailleHeads Password Reset Request',sender='noreply@dummy.com',recipients=[user.email])
    msg.body=f'''To reset your password, visit the following link:{url_for('reset_token',token=token,_external=True)}
    
If you did not make this request, simply ignore this email!
    '''
    mail.send(msg)
  
def is_pdf_empty(filepath):
    try:
        with fitz.open(filepath) as pdf:
            if pdf.page_count == 0:
                return True
            else:
                page = pdf.load_page(0)
                text = page.get_text("text")
                if len(text.strip()) == 0:
                    return True
                else:
                    return False
    except Exception as e:
        return True
            
def reader(filename):
    doc = fitz.open(filename)
    text = ""
    for page in doc:
        text+=page.get_text()
    return text
    
def text_to_pdf(text, filename):
    a4_width_mm = 210
    pt_to_mm = 0.35
    fontsize_pt = 10
    fontsize_mm = fontsize_pt * pt_to_mm
    margin_bottom_mm = 10
    character_width_mm = 7 * pt_to_mm
    width_text = a4_width_mm / character_width_mm

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(True, margin=margin_bottom_mm)
    pdf.add_font('DejaVu','',r'DejaVuSansCondensed.ttf',uni=True)
    pdf.add_page()
    pdf.set_font('DejaVu','', size=fontsize_pt)
    splitted=text.split('\n')
    for line in splitted:
        lines = textwrap.wrap(line, width_text)

        if len(lines) == 0:
            pdf.ln()

        for wrap in lines:
            pdf.cell(0, fontsize_mm, wrap, ln=1)
    pdf.output(filename, 'F') 

    
def text_to_speech(text, filename):
    tts = gTTS(text, lang='en-uk')
    tts.save(filename)
    
def pdf_out(filename): 
      
    text=reader(filename)
    
    text=(alphaToBraille.translate(text))
    
    text_to_pdf(text, current_user.username+"_BrailleHeads-convt.pdf")
    
#app configurations
    
app=Flask(__name__)
app.config['SECRET_KEY']='42c96012a2ced65b2743be7bf5933576'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///'+ os.path.join(app.root_path, 'site.db')

db=SQLAlchemy(app)

#models
class User(db.Model,UserMixin):
    id= db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(20), unique=True, nullable=False)
    email=db.Column(db.String(220), unique=True, nullable=False)
    password=db.Column(db.String(60), nullable=False)
    
    def get_reset_token(self, expires_sec=1800):
        sayonara=ser(app.config['SECRET_KEY'],expires_sec)
        return sayonara.dumps({'user_id':self.id}).decode('utf-8')
    
    @staticmethod
    def verify_reset_token(token):
        sayonara=ser(app.config['SECRET_KEY'])
        try:
            user_id=sayonara.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)        
        
    
    def __repr__(self):
        return f"User('{self.username}','{self.email}')"


login_manager=LoginManager(app)
#loginManager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
 
bcrypt=Bcrypt(app)
app.config['MAIL_SERVER']='smtp.googlemail.com'
app.config['MAIL_PORT']=587
app.config['MAIL_USE_TLS']=True
app.config['MAIL_USERNAME']="arakuro98@gmail.com"
app.config['MAIL_PASSWORD']=""
mail=Mail(app)

#forms
class RegForm(FlaskForm):
    username=StringField('Username',
                         validators=[DataRequired(),Length(min=2,max=20)])
    email=StringField("Email",
                      validators=[DataRequired(),Email()])
    password=PasswordField("Password",
                           validators=[DataRequired()])
    confirm_password=PasswordField("Confirm Password",
                           validators=[DataRequired(),EqualTo('password')])
    submit=SubmitField('Sign Up')
    
    def validate_username(self,username):
        user=User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username seems to be taken. Please choose a unique one')
    
    def validate_email(self,email):
        user=User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email seems to be taken. Please choose a unique one')
    

class LoginForm(FlaskForm):
    email=StringField("Email",
                      validators=[DataRequired(),Email()])
    password=PasswordField("Password",
                           validators=[DataRequired()])
    remember=BooleanField("Remember Me")
    submit=SubmitField('Login')

class RequestResetForm(FlaskForm):
    email=StringField("Email",
                      validators=[DataRequired(),Email()])
    submit=SubmitField('Request Password Reset')
    
    def validate_email(self,email):
        user=User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('There is no account with that email. You must register first!')

class ResetPassword(FlaskForm):
    password=PasswordField("Password",
                           validators=[DataRequired()])
    confirm_password=PasswordField("Confirm Password",
                           validators=[DataRequired(),EqualTo('password')])
    submit=SubmitField('Reset Password')
    

#routing paths
@app.route('/work')
def home():
    if current_user.is_authenticated:
        with app.app_context():
            return render_template('front.html',name=alphaToBraille.n)
    return redirect(url_for('log'))



@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if current_user.is_authenticated:
        pdf_file = request.files['pdf_file']
        alphaToBraille.n=pdf_file.filename
        pdf_file.save(current_user.username+"upload.pdf")
        if is_pdf_empty(current_user.username+"upload.pdf"):
            flash('No File was uploaded / Wrong format!', 'danger')
        else:
            flash(pdf_file.filename+' was uploaded Successfully!', 'success')
        return redirect(url_for('home'))
    return redirect(url_for('log'))
    

@app.route('/register',methods=['GET','POST'])
def reg():
    if current_user.is_authenticated:
            flash(f'You are already Logged in as {current_user.username} !','success')
            return redirect(url_for('home'))
    form=RegForm()
    if form.validate_on_submit():
        hashed_pass=bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user=User(username=form.username.data, email=form.email.data, password=hashed_pass)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created for {form.username.data}! Login to Continue!','success')
        return redirect(url_for('log'))
    return render_template('register.html',form=form)

@app.route('/',methods=['GET','POST'])
def log():
    if current_user.is_authenticated:
            flash(f'Logged in as {current_user.username} !','success')
            return redirect(url_for('home'))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user,remember=form.remember.data)
            flash(f'Logged in Successfully!','success')
            return redirect(url_for('home'))
        else:
            flash("Login Unsuccessful! Please recheck the email and password!","danger")
    return render_template('login.html',form=form)
    
@app.route('/cnvt')
def my_function():
    if os.path.exists(current_user.username+'upload.pdf'):
        pdf_out(current_user.username+"upload.pdf")
        return send_file(current_user.username+"_BrailleHeads-convt.pdf", as_attachment=True) 
    else:
        return "<p>Please Upload File and Try Again!<p>"

@app.route('/logout')
def lout():
    if os.path.exists(current_user.username+'upload.pdf'):
        os.remove(current_user.username+'upload.pdf')
    if os.path.exists(current_user.username+'_BrailleHeads-convt.mp3'):
        os.remove(current_user.username+'_BrailleHeads-convt.mp3')
    if os.path.exists(current_user.username+"_BrailleHeads-convt.pdf"):
        os.remove(current_user.username+"_BrailleHeads-convt.pdf")
    logout_user()
    res=redirect(url_for('log'))
    flash(f'Logged Out !','danger')
    return res

@app.route('/send_mp3')
def send_mp3():
    
    if os.path.exists(current_user.username+'upload.pdf'):
        text=reader(current_user.username+"upload.pdf")
        alphaToBraille.n="No FILE"
        text_to_speech(text,current_user.username+'_BrailleHeads-convt.mp3')
        file_path = current_user.username+'_BrailleHeads-convt.mp3'
    else:
        text="No file was uploaded!"
        alphaToBraille.n="No FILE"
        text_to_speech(text,current_user.username+'_BrailleHeads-convt.mp3')
        file_path = current_user.username+'_BrailleHeads-convt.mp3'
    return send_file(file_path, mimetype='audio/mp3',as_attachment=True) 

@app.route('/reset_password',methods=['GET','POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=RequestResetForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash("An email has been sent with instructions to reset your password!",'info')
        return redirect(url_for('log'))
    return render_template('reset_request.html',form=form)

@app.route("/reset_password/<token>",methods=['GET','POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user=User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token','warning')
        return redirect(url_for('reset_request'))
    form=ResetPassword()
    if form.validate_on_submit():
        hashed_pass=bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password=hashed_pass
        db.session.commit()
        flash(f'Password has been updated!','success')
        return redirect(url_for('log'))

    return render_template('reset_token.html',form=form)


if __name__=='__main__':
    app.run(debug=True)
    # with app.app_context():
    #     db.drop_all()
    #     db.create_all()