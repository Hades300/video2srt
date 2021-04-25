import hashlib
import hmac

def md5(text: str)->str:
    return hashlib.md5(text.encode('utf8')).digest().hex()

def sha1(payload:str,key:str="")->str:
    """sha1 encode
    params:
        payload: 
        key: 可选的秘钥，若留空，则仅进行sha1加密
    """
    if not key:
        return hashlib.sha1(payload.encode()).hexdigest()
    return hmac.new(key.encode(),payload.encode(),hashlib.sha1).hexdigest()


if __name__=="__main__":
    print(sha1("a","b"))
