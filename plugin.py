###
# Copyright (c) 2007, Mike McGrath
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import sgmllib
import htmlentitydefs

import supybot.utils as utils
import supybot.conf as conf
from datetime import datetime
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import simplejson
import urllib
import commands

## Maximum number of days to cache the owners.list file
MAX_OWNERS_AGE = 3

## We'll pull the list from CVS until we can get it from the Package Database
OWNERS_URL = "https://admin.fedoraproject.org/pkgdb/acls/bugzilla?tg_format=plain"



class Title(sgmllib.SGMLParser):
    entitydefs = htmlentitydefs.entitydefs.copy()
    entitydefs['nbsp'] = ' '
    def __init__(self):
        self.inTitle = False
        self.title = ''
        sgmllib.SGMLParser.__init__(self)

    def start_title(self, attrs):
        self.inTitle = True

    def end_title(self):
        self.inTitle = False

    def unknown_entityref(self, name):
        if self.inTitle:
            self.title += ' '

    def unknown_charref(self, name):
        if self.inTitle:
            self.title += ' '

    def handle_data(self, data):
        if self.inTitle:
            self.title += data


class Fedora(callbacks.Plugin):
    """Add the help for "@plugin help Fedora" here
    This should describe *how* to use this plugin."""
    threaded = True

     # Our owners.list
    owners = None

    # Timestamp of our owners data
    timestamp = None 

    def _getowners(self):
        """
        Return the owners list.  If it's not already cached, grab it from
        OWNERS_URL, and use it for MAX_OWNERS_AGE days
        """
        if self.owners != None:
            if (datetime.now() - self.timestamp).days <= MAX_OWNERS_AGE:
                return self.owners
        self.owners = utils.web.getUrl(OWNERS_URL)
        self.timestamp = datetime.now()
        return self.owners

    def whoowns(self, irc, msg, args, package):
        """<package>

        Retrieve the owner of a given package
        """
        owners_list = self._getowners()
        owner = None
        for line in owners_list.split('\n'):
            entry = line.strip().split('|')
            if len(entry) >= 5:
                if entry[1] == package:
                    owner = entry[3]
                    break
        irc.reply("%s" % owner)
    whoowns = wrap(whoowns, ['text'])

   

    def fas(self, irc, msg, args, name):
        file = open('/home/mmcgrath/supybot/accounts.txt')
        find_name = name
        found = 0
        mystr = []
        for f in file.readlines():
            #if not f.lower().find(find_name.lower()):
            #    continue
            try:
                (username, email, name, type, number) = f.strip().split(',')
                if username == find_name.lower() or email.lower().find(find_name.lower()) != -1 or name.lower().find(find_name.lower()) != -1:
                    mystr.append(str("%s '%s' <%s>" % (username, name, email)))
                    found += 1
            except:
                try:
                    (username, email, name, name2, type, number) = f.strip().split(',')
                    if username == find_name.lower() or email.lower().find(find_name.lower()) != -1 or name.lower().find(find_name.lower()) != -1 or name2.lower().find(find_name) != -1:
                        irc.reply(str(" %s '%s %s' <%s>" % (username, name, name2, email)))
                        found = 1
                except:
                    pass
        if found == 0:
            irc.reply(str("'%s' Not Found!" % find_name))
        else:
            irc.reply(' - '.join(mystr))
    fas = wrap(fas, ['text'])

    def fasinfo(self, irc, msg, args, name):
        #file = open('/home/mmcgrath/supybot/accounts.txt')
        if len(name) > 14:
            irc.reply(str('Error getting info for user: "%s"' % name))
            return
        url = commands.getoutput('/usr/bin/wget -qO- "https://admin.fedoraproject.org/accounts/user/view/%s?tg_format=json&login=Login&user_name=&password="' % name)
        try:
            info = simplejson.read(url)['person']
        except ValueError:
            irc.reply(str('Error getting info for user: "%s"' % name))
            return

        string = "User: %s, Name: %s, email: %s Creation: %s, IRC Nick: %s, Timezone: %s, Locale: %s, Extension: 5%s" % (info['username'], info['human_name'], info['email'], info['creation'].split(' ')[0], info['ircnick'], info['timezone'], info['locale'], info['id'])
        approved = ''
        for group in info['approved_memberships']:
            approved = approved + "%s " % group['name']

        unapproved = ''
        for group in info['unapproved_memberships']:
            unapproved = unapproved + "%s " % group['name']

        if approved == '':
            approved = "None"
        if unapproved == '':
            unapproved = "None"

        irc.reply(str(string.encode('utf-8')))
        irc.reply(str('Approved Groups: %s' % approved))
        irc.reply(str('Unapproved Groups: %s' % unapproved))
    fasinfo = wrap(fasinfo, ['text'])



    def ticket(self, irc, msg, args, num):
        """<url>

        Returns the HTML <title>...</title> of a URL.
        """
        url = 'https://fedorahosted.org/projects/fedora-infrastructure/ticket/%s' % num
        size = conf.supybot.protocols.http.peekSize()
        text = utils.web.getUrl(url, size=size)
        parser = Title()
        try:
            parser.feed(text)
        except sgmllib.SGMLParseError:
            self.log.debug('Encountered a problem parsing %u.  Title may '
                           'already be set, though', url)
        if parser.title:
            irc.reply(str("%s - https://fedorahosted.org/projects/fedora-infrastructure/ticket/%s" % (utils.web.htmlToText(parser.title.strip()), num) ))
        else:
            irc.reply(format('That URL appears to have no HTML title '
                             'within the first %i bytes.', size))
    ticket = wrap(ticket, ['int'])

    def rel(self, irc, msg, args, num):
        """<url>

        Returns the HTML <title>...</title> of a URL.
        """
        url = 'https://fedorahosted.org/projects/rel-eng/ticket/%s' % num
        size = conf.supybot.protocols.http.peekSize()
        text = utils.web.getUrl(url, size=size)
        parser = Title()
        try:
            parser.feed(text)
        except sgmllib.SGMLParseError:
            self.log.debug('Encountered a problem parsing %u.  Title may '
                           'already be set, though', url)
        if parser.title:
            irc.reply(str("%s - https://fedorahosted.org/projects/rel-eng/ticket/%s" % (utils.web.htmlToText(parser.title.strip()), num) ))
        else:
            irc.reply(format('That URL appears to have no HTML title '
                             'within the first %i bytes.', size))
    rel = wrap(rel, ['int'])


    def swedish(self, irc, msg, args):
        irc.reply(str('kwack kwack'))
        irc.reply(str('bork bork bork'))
    swedish = wrap(swedish)


    def bug(self, irc, msg, args, url):
        """<url>

        Returns the HTML <title>...</title> of a URL.
        """
        bugNum = url
        url = 'https://bugzilla.redhat.com/show_bug.cgi?id=%s' % url
        size = conf.supybot.protocols.http.peekSize()
        text = utils.web.getUrl(url, size=size)
        parser = Title()
        try:
            parser.feed(text)
        except sgmllib.SGMLParseError:
            self.log.debug('Encountered a problem parsing %u.  Title may '
                           'already be set, though', url)
        if parser.title:
            irc.reply("%s - https://bugzilla.redhat.com/%i" % (utils.web.htmlToText(parser.title.strip()), bugNum))
        else:
            irc.reply(format('That URL appears to have no HTML title '
                             'within the first %i bytes.', size))
    bug = wrap(bug, ['int'])


Class = Fedora


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
