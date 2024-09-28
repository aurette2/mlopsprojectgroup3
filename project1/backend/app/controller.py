from fastapi import FastAPI, File, UploadFile, HTTPException, status, Depends 
from datetime import datetime, timedelta, timezone
from typing import Union
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from PIL import Image
import io
import os
import tempfile

from dotenv import load_dotenv
from passlib.context import CryptContext
import jwt
from jwt import PyJWTError
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modelblip import BlipMed

load_dotenv()
# JWT settings 
SECRET_KEY = os.getenv('SECRET_KEY')  # Replace with your own secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Initialize the FastAPI application
app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# User database
users_db = {
    "admin": {"username": "admin", "password": pwd_context.hash("adminpass"), "role": "admin"},
    "user": {"username": "user", "password": pwd_context.hash("userpass"), "role": "user"},
}

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(username: str, password: str):
    user = users_db.get(username)
    if not user or not verify_password(password, user["password"]):
        return False
    return user

def create_access_token(data: dict, role: str, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    to_encode.update({"role": role})  # Add role to the payload
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=45)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        return payload
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

# Load model and processor
global blipMed 
blipMed = BlipMed()


@app.get('/')
async def get_hello():
    return{"User": "Welcome to MLOPS"}


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, role=user["role"], expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/generate_report/")
async def generate_report(file: UploadFile = File(...), indication: str = None, token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    username = payload.get("sub")
    try:
        image_data = await file.read()  
        image = Image.open(io.BytesIO(image_data))  

        report = blipMed.generate_report(image=image, my_indication=indication)

        return {"report": report, "radiologist_name": users_db.get(username)}
    
    except Exception as e:
        return {"error": str(e)}
   
    
@app.get('/show_drift')
async def show_drift(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    role = payload.get("role")
    
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    
    return{"Only Admin": "Welcome to MLOPS DATA drift"}


@app.post('/vqa')
async def question_image(question: str, file: UploadFile = File(...), token: str = Depends(oauth2_scheme) ):
    # username = decode_token(token)
    try:
        image_data = await file.read()  
        image = Image.open(io.BytesIO(image_data)) 
       
        return{"question": question}
        
    except Exception as e:
        return {"error": str(e)}
        

    
