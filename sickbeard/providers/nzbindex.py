# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

import re
import time
import urllib
import datetime

from xml.dom.minidom import parseString     

import sickbeard
import generic

from sickbeard import classes, logger, show_name_helpers
from sickbeard import tvcache
from sickbeard.exceptions import ex

class NZBIndexProvider(generic.NZBProvider):

    def __init__(self):

        generic.NZBProvider.__init__(self, "NZBIndex")

        self.supportsBacklog = True

        self.cache = NZBIndexCache(self)

        self.url = 'http://www.nzbindex.nl/'
        self.lastSearchStrings = []
        self.lastSearchTime = None

    def isEnabled(self):
        return sickbeard.NZBINDEX

    def _get_season_search_strings(self, show, season):
        # sceneSearchStrings = set(show_name_helpers.makeSceneSeasonSearchString(show, season, "NZBIndex"))

        # # search for all show names and episode numbers like ("a","b","c") in a single search
        # return [' '.join(sceneSearchStrings)]
        return [x for x in show_name_helpers.makeSceneSeasonSearchString(show, season)]

    def _get_episode_search_strings(self, ep_obj):
        # # tvrname is better for most shows
        # if ep_obj.show.tvrname:
        #     searchStr = ep_obj.show.tvrname + " S%02dE%02d"%(ep_obj.season, ep_obj.episode)
        # else:
        #     searchStr = ep_obj.show.name + " S%02dE%02d"%(ep_obj.season, ep_obj.episode)
        # return [searchStr]
        return [x for x in show_name_helpers.makeSceneSearchString(ep_obj)]

    def _get_title_and_url(self, item):
        (title, url) = super(NZBIndexProvider, self)._get_title_and_url(item)
        newTitle = []
        logger.log( '_get_title_and_url(%s), returns (%s, %s)' %(item, title, url), logger.DEBUG)
        logger.log( 'self.lastSearchStrings = "%s"' % self.lastSearchStrings, logger.DEBUG)

        # try to filter relevant parts from title
        splitTitle = re.sub( '\s+|\'|"|\.par2', ' ', re.sub('[\[\]\(\)\<\>]+', ' ', title) ).strip().split()
        # newTitle = filter( lambda x: x.lower().startswith( self.searchString.lower().strip().split()[0] ), splitTitle )

        for t in splitTitle:
            for searchString in self.lastSearchStrings:
                if t.lower().strip().startswith( searchString.lower().strip().split()[0] ) and not t in newTitle:
                    newTitle.append( t )
        
        if len(newTitle) > 1:
            logger.log( 'more than one result for the fixed title (%s), using first.' % newTitle, logger.ERROR )
        if newTitle:
            newTitle = newTitle[0]
            logger.log( 'fixed title: "%s"' % newTitle, logger.DEBUG)
            return (newTitle, url)

        # Fallback to oritinal title if we had no success
        logger.log( 'Could not fix title...', logger.DEBUG)
        return (title, url)
            

    def _doSearch(self, curString, quotes=False, show=None):
        #term =  re.sub('[\.\-]', ' ', curString).encode('utf-8')
        term =  curString.encode('utf-8')

        if quotes:
            term = "\""+term+"\""

        # FIXME: How to get wanted quality here to improve results?
        # term += ' 720p'

        params = {"q": term,
                  "max": 200,
                  "hidespam": 1,
                  'complete': 1,
                  "minsize":100,
                  "nzblink":1}

        searchURL = "http://nzbindex.nl/rss/?" + urllib.urlencode(params)
        logger.log(u"Search URL: " + searchURL)

        # Sleep 10sec between querys
        if self.lastSearchTime:
            sleepSecs = (self.lastSearchTime + 10) - time.time()
            if sleepSecs > 0:
                logger.log(u"Sleeping %f seconds to respect NZBIndex's rules" % sleepSecs)
                time.sleep( sleepSecs )

        searchResult = self.getURL(searchURL,[("User-Agent","Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:5.0) Gecko/20100101 Firefox/5.0"),("Accept","text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),("Accept-Language","de-de,de;q=0.8,en-us;q=0.5,en;q=0.3"),("Accept-Charset","ISO-8859-1,utf-8;q=0.7,*;q=0.7"),("Connection","keep-alive"),("Cache-Control","max-age=0")])
        self.lastSearchTime = time.time()

        if not searchResult:
            return []

        try:
            parsedXML = parseString(searchResult)
            items = parsedXML.getElementsByTagName('item')
        except Exception, e:
            logger.log(u"Error trying to load NZBIndex RSS feed: "+ex(e), logger.ERROR)
            return []

        results = []

        for curItem in items:
            (title, url) = self._get_title_and_url(curItem)

            if not title or not url:
                logger.log(u"The XML returned from the NZBIndex RSS feed is incomplete, this result is unusable", logger.ERROR)
                continue
            if not title == 'Not_Valid':
                results.append(curItem)

        return results

    def findEpisode(self, episode, manualSearch=False):
        '''
        Cache search stings for better results from _get_title_and_url
        '''
        self.lastSearchStrings = self._get_episode_search_strings(episode)
        return super(NZBIndexProvider, self).findEpisode(episode, manualSearch)
    def findSeasonResults(self, show, season):
        '''
        Cache search stings for better results from _get_title_and_url
        '''
        self.lastSearchStrings = self._get_season_search_strings(show, season)
        return super(NZBIndexProvider, self).findSeasonResults(show, season)

    def findPropers(self, date=None):

        results = []

        for curResult in self._doSearch("(PROPER,REPACK)"):

            (title, url) = self._get_title_and_url(curResult)

            pubDate_node = curResult.getElementsByTagName('pubDate')[0]
            pubDate = helpers.get_xml_text(pubDate_node)
            dateStr = re.search('(\w{3}, \d{1,2} \w{3} \d{4} \d\d:\d\d:\d\d) [\+\-]\d{4}', pubDate)
            if not dateStr:
                logger.log(u"Unable to figure out the date for entry "+title+", skipping it")
                continue
            else:
                resultDate = datetime.datetime.strptime(match.group(1), "%a, %d %b %Y %H:%M:%S")

            if date == None or resultDate > date:
                results.append(classes.Proper(title, url, resultDate))

        return results


class NZBIndexCache(tvcache.TVCache):

    def __init__(self, provider):

        tvcache.TVCache.__init__(self, provider)

        # only poll NZBIndex every 25 minutes max
        self.minTime = 25


    def _getRSSData(self):
        # get all records since the last timestamp
        url = "http://nzbindex.nl/rss/?"

        urlArgs = {'q': '',
                   'max': 50,
                   'sort': 'agedesc',
                   'hidespam': 1,
                   'complete': 1,
                   'minsize':100,
                   'nzblink':1}

        url += urllib.urlencode(urlArgs)

        logger.log(u"NZBIndex cache update URL: "+ url, logger.DEBUG)

        data = self.provider.getURL(url)

        return data


provider = NZBIndexProvider()
