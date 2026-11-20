# Recebe texto enviado pelo navegador (POST em http://127.0.0.1:8765/<nome>) e grava em banco/fonte_tec/recebidos/<nome>.json
import http.server, pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "banco" / "fonte_tec" / "recebidos"; OUT.mkdir(parents=True, exist_ok=True)
class H(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(s):
        s.send_response(204); s.send_header("Access-Control-Allow-Origin","*"); s.send_header("Access-Control-Allow-Headers","*"); s.send_header("Access-Control-Allow-Private-Network","true"); s.end_headers()
    def do_POST(s):
        n = int(s.headers.get("Content-Length", 0)); body = s.rfile.read(n)
        nome = "".join(c for c in s.path.strip("/") if c.isalnum() or c in "-_") or "sem_nome"
        (OUT / (nome + ".json")).write_bytes(body)
        s.send_response(200); s.send_header("Access-Control-Allow-Origin","*"); s.end_headers(); s.wfile.write(b"ok")
    def log_message(s,*a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
