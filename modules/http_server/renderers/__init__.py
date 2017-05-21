
class SimplePageRenderer(object):
    title = "This is a page."
    head = ""
    body = "Yeah, a really simple page."

    def set_title(self, title):
        self.title = title

    def set_body(self, body):
        self.body = body

    def render(self):
        return """<html><head>%s<title>%s</title></head><body>%s</body></html>""" % (
            self.head, self.title, self.body)
