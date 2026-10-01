import os
from pathlib import Path
import subprocess
import sys

def test_fk_on_own_domain(tmp_path):
    env=dict(os.environ,SITE_MODE='kaka',SECRET_KEY='standalone-test-secret',
       KAKA_DB=str(tmp_path/'kaka.db'),TRIADE_AUTH_DB=str(tmp_path/'accounts.db'))
    code='''
from app import app
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlsplit
client=app.test_client()
for path in ['/', '/servicos','/login','/criar-conta']:
    response=client.get(path)
    assert response.status_code==200,path
    soup=BeautifulSoup(response.data,'html.parser')
    for node in soup.select('img[src],script[src],link[rel=stylesheet]'):
        target=urlsplit(urljoin('http://localhost'+path,node.get('src') or node.get('href')))
        if target.hostname=='localhost': assert client.get(target.path).status_code==200,target.path
assert client.get('/admin').location=='/admin/login'
assert client.get('/sectest/').status_code==404
print('standalone OK')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
