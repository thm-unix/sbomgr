#!/usr/bin/python3

import os
import sys
import stat
import requests
import wget
import tarfile
from collections import deque


def downloadPage(url):
    return requests.get(url).text


def downloadFile(url):
    filename = wget.download(url)
    return filename


def listDependencies(webPage):
    deps = []
    if 'This requires:' in webPage:
        reqStart = webPage.index('This requires:')
        reqEnd = webPage.index('Maintained by:')
        reqLine = webPage[reqStart:reqEnd]
        reqLineStart = reqLine.index(': ') + 2
        reqLineEnd = reqLine.index('</p>')
        reqLine = reqLine[reqLineStart:reqLineEnd]

        for dep in reqLine.split(', '):
            depStart = dep.index('=\'') + 2
            depEnd = dep.index('\'>')
            deps += [dep[depStart:depEnd]]

    return deps


def downloadPackage(url, webPage, installQueue):
    packageName = url[:-1].split('/')[-1]
    packageURL = url.split('/')
    packagePath = '/'.join(packageURL[4:])

    webPageStart = webPage.index('Download SlackBuild:')
    webPageEnd = webPage.index('(the SlackBuild')
    webPage = webPage[webPageStart:webPageEnd]
    sbURLStart = webPage.index('=\"') + 2
    sbURLEnd = webPage.index('\">')
    sbURL = f'http://slackbuilds.org{webPage[sbURLStart:sbURLEnd]}'

    infoURL = f'http://slackbuilds.org/slackbuilds/{packagePath}{packageName}.info'
    info = downloadPage(infoURL)
    srcURLStart = info.index('DOWNLOAD=\"') + 10
    srcURL = info[srcURLStart:]
    srcURLEnd = srcURL.index('\"')
    srcURL = srcURL[:srcURLEnd]

    os.mkdir(packageName)
    os.chdir(packageName)
    print(f'Downloading {sbURL}...')
    downloadFile(sbURL)
    print(f'Downloading {srcURL}...')
    downloadFile(srcURL)
    os.chdir('..')

    return (sbURL, srcURL)


def makePackage(packageName, srcFilename):
    os.chdir(packageName)

    tar = tarfile.open(f'{packageName}.tar.gz', 'r:gz')
    tar.extractall()
    tar.close()

    os.rename(srcFilename, f'{packageName}/{srcFilename}')
    os.chdir(packageName)
    sbFile = f'{packageName}.SlackBuild'
    st = os.stat(sbFile)
    os.chmod(sbFile, st.st_mode | stat.S_IEXEC)
    os.system(f'./{sbFile}')


if __name__ == '__main__':
    if os.getenv('USER') == 'root':
        #url = sys.argv[1]
        url = 'https://slackbuilds.org/repository/15.0/development/notepadqq/'
        packageName = url[:-1].split('/')[-1]
        installQueue = deque()

        page = downloadPage(url)
        files = downloadPackage(url, page, installQueue)
        srcFileName = files[1]
        if srcFileName.endswith('/'):
            srcFileName = srcFileName[:-1]
        srcFileName = srcFileName.split('/')[-1]
        makePackage(packageName, srcFileName)
    else:
        print('Run it as root.')
