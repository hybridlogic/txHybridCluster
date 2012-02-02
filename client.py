#!/usr/bin/env python

from twisted.internet import defer
import utils
import pprint

class HybridClusterException(Exception):
    """
    An exception raised by the Control Panel's XML API.  The exception value is
    the ElementTree of the XML response's Errors element.
    """
    def __init__(self, xml, cmd, query):
        self.xml = xml
        self.cmd = cmd
        self.query = query

    def __str__(self):
        return ("\n    " + (str(self.xml) if isinstance(self.xml, list) else str(utils.tostring(self.xml))) +
                "\nRunning: " + self.cmd +
                "\nQuery: " + pprint.pformat(self.query))


class Client(object):
    """
    Simple wrapper for the Control Panel XML API, returning responses using the
    ElementTree API.

    Smallest working example:

    >>> api = Client("my.cluster.com", "resellername", "somepass")
    >>> yield api.testSuccess()
    >>> print "Got a successful response from the API"

    Error case:

    >>> try:
    >>>     yield api.testFail()
    >>> except HybridClusterException, e:
    >>>     print "Got error:", e

    Should print "Got Error: Failed test command."

    Something more interesting, creating a website and fetching its website ID:

    >>> websiteID = int((yield api.addExternalDomain(
    >>>                      Domain='mydomain.com',
    >>>                      Type='blank',
    >>>                 )).find('WebsiteID').text)
    """

    def __init__(self, cpDomain, username, password, apiVersion='1.1', decodeResponse=False):
        self.endpoint = "http://%s/api/post" % (cpDomain)
        self.username = username
        self.password = password
        self.apiVersion = apiVersion
        self.decodeResponse = decodeResponse


    def __getattr__(self, funcname):
        command = funcname.upper()
        def inner(**kw):
            query = {
                        'Reseller':        self.username,
                        'APIKey':          self.password,
                        'Command':         command,
                        'APIVersion':      self.apiVersion,
                    }
            query.update(kw)
            if self.decodeResponse:
                query['ResponseFormat'] = "json"
            d = utils.httpRequest(self.endpoint,
                    query,
                    headers={'Content-Type': ['application/x-www-form-urlencoded']}
                )
            def parse(xml):
                if self.decodeResponse:
                    from simplejson import loads
                    from simplejson.decoder import JSONDecodeError
                    try:
                        return loads(xml)
                    except JSONDecodeError:
                        raise Exception("Could not decode JSON '%s'" % xml)
                try:
                    result = utils.fromstring(xml)
                except Exception:
                    print "Trying to parse", xml
                    raise
                return result
            d.addCallback(parse)
            def checkErrors(xml):
                if self.decodeResponse:
                    if int(xml['ErrorCount'] > 0):
                        raise HybridClusterException(xml['Errors'], command, query)
                else:
                    if int(xml.find('ErrorCount').text) > 0:
                        raise HybridClusterException(xml.find('Errors'), command, query)
                return xml
            d.addCallback(checkErrors)
            return d
        return inner



@defer.inlineCallbacks
def pollStepAction(api, stepActionID):
    """
    Poll the given stepActionID until all the consituent steps are
    complete, then fire the returned deferred.
    """
    numStepActions = 0
    completedStepActions = None
    while completedStepActions < numStepActions:
        response = yield api.pollStepAction(StepActionID=stepActionID)
        steps = response.find("Steps").getchildren()
        numStepActions = 0
        completedStepActions = 0
        print "\n"
        for step in steps:
            status = step.find("Description").text.ljust(40, '.')
            numStepActions += 1
            if step.find("CompleteDate") is not None:
                completedStepActions += 1
                status += "FINISHED"
            else:
                status += "PENDING"
            print status
        yield utils.sleep(1)
