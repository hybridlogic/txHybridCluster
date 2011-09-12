from twisted.internet.defer import succeed
from twisted.internet import defer, protocol
from twisted.internet import reactor
from twisted.python.reflect import ObjectNotFound, namedAny
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implements
import urllib

def tryImports(*names):
    for name in names:
        try:
            return namedAny(name)
        except ObjectNotFound:
            pass
    raise

etree = tryImports('lxml.etree', 'xml.etree.ElementTree')
Element = tryImports('lxml.etree.Element', 'xml.etree.ElementTree.Element')

ElementType = type(etree.Element("type"))

tostring = etree.tostring
fromstring = etree.fromstring


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass



def httpRequest(url, values={}, headers={}, method='POST'):
    # Construct an Agent.
    agent = Agent(reactor)
    data = urllib.urlencode(values)

    if method == "POST" and values:
        headers['Content-Type'] = ["application/x-www-form-urlencoded"]

    d = agent.request(method,
                      url,
                      Headers(headers),
                      StringProducer(data) if data else None)

    def handle_response(response):
        if response.code == 204:
            d = defer.succeed('')
        else:
            class SimpleReceiver(protocol.Protocol):
                def __init__(s, d):
                    s.buf = ''; s.d = d
                def dataReceived(s, data):
                    s.buf += data
                def connectionLost(s, reason):
                    # TODO: test if reason is twisted.web.client.ResponseDone,
                    # if not, do an errback
                    s.d.callback(s.buf)

            d = defer.Deferred()
            response.deliverBody(SimpleReceiver(d))
        return d

    d.addCallback(handle_response)
    return d


def sleep(secs, data=None):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, data)
    return d

