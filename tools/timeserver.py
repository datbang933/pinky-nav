import http.server, time
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        b = ('%.6f' % time.time()).encode(); s.send_response(200); s.send_header('Content-Length', str(len(b))); s.end_headers(); s.wfile.write(b)
    def log_message(s, *a): pass
http.server.HTTPServer(('0.0.0.0', 8765), H).serve_forever()
