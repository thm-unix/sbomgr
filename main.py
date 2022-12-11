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

    return -1


def downloadPackage(url, name, webPage):
    urlList = url.split('/')
    packagePath = '/'.join(urlList[4:])

    print(url)
    webPageStart = webPage.index('Download SlackBuild:')
    webPageEnd = webPage.index('(the SlackBuild')
    webPage = webPage[webPageStart:webPageEnd]
    sbURLStart = webPage.index('=\"') + 2
    sbURLEnd = webPage.index('\">')
    sbURL = f'http://slackbuilds.org{webPage[sbURLStart:sbURLEnd]}'

    infoURL = f'http://slackbuilds.org/slackbuilds/{packagePath}{name}.info'
    info = downloadPage(infoURL)
    srcURLStart = info.index('DOWNLOAD=\"') + 10
    srcURL = info[srcURLStart:]
    srcURLEnd = srcURL.index('\"')
    srcURL = srcURL[:srcURLEnd]

    os.mkdir(name)
    os.chdir(name)
    print(f'Downloading {sbURL}...')
    downloadFile(sbURL)
    print(f'Downloading {srcURL}...')
    downloadFile(srcURL)
    os.chdir('..')

    return sbURL, srcURL


def makePackage(name, srcFilename):
    os.chdir(name)

    tar = tarfile.open(f'{name}.tar.gz', 'r:gz')
    tar.extractall()
    tar.close()

    os.rename(srcFilename, f'{name}/{srcFilename}')
    os.chdir(name)
    sbFile = f'{name}.SlackBuild'
    st = os.stat(sbFile)
    os.chmod(sbFile, st.st_mode | stat.S_IEXEC)
    os.system(f'./{sbFile}')


def installPkg(name):
    sbFilename = f'{name}.SlackBuild'
    slackBuild = ''
    with open(sbFilename, 'r') as slackBuildReader:
        slackBuild = slackBuildReader.read()

    nameStartIndex = slackBuild.index('PRGNAM=')
    nameEndIndex = slackBuild[nameStartIndex:].index('\n')
    PRGNAM = slackBuild[nameStartIndex+7:nameStartIndex+nameEndIndex]

    versionStartIndex = slackBuild.index('VERSION=')
    versionEndIndex = slackBuild[versionStartIndex:].index('\n')
    VERSION = slackBuild[versionStartIndex+8:versionStartIndex+versionEndIndex]

    ARCH = os.popen('uname -m').read()

    buildStartIndex = slackBuild.index('BUILD=')
    buildEndIndex = slackBuild[buildStartIndex:].index('\n')
    BUILD = slackBuild[buildStartIndex+6:buildStartIndex+buildEndIndex]

    tagStartIndex = slackBuild.index('TAG=')
    tagEndIndex = slackBuild[tagStartIndex:].index('\n')
    TAG = slackBuild[tagStartIndex+4:tagStartIndex+tagEndIndex]

    typeStartIndex = slackBuild.index('PKGTYPE=')
    typeEndIndex = slackBuild[typeStartIndex:].index('\n')
    PKGTYPE = slackBuild[typeStartIndex+8:typeStartIndex+typeEndIndex]

    pkgPath = f'/tmp/{PRGNAM}-{VERSION}-{ARCH}-{BUILD}{TAG}.{PKGTYPE}'

    os.chdir('/tmp')
    os.system(f'upgrade-pkg --install-new {pkgPath}')


def queuePkgs(pkgURL, queue):
    queue.append(pkgURL)
    deps = listDependencies(downloadPage(f'http://slackbuilds.org/{pkgURL}'))
    if deps != -1:
        for dep in deps:
            if dep not in queue:
                queuePkgs(dep, queue)
            else:
                print('!! WARNING !! Cycle dependency found!')
                pkgName = pkgURL[:-1].split('/')[-1]
                depName = dep[:-1].split('/')[-1]
                print(f'{pkgName} -> {depName}')
                exit(1)
    else:
        return


def sequence(pkgURL):
    workdir = os.getcwd()
    pkgName = pkgURL[:-1].split('/')[-1]
    installQueue = deque()
    queuePkgs(pkgURL, installQueue)

    while installQueue:
        elem = '/'.join(installQueue.pop().split('/')[2:])
        currentURL = f'http://slackbuilds.org/repository/{elem}'
        pkgName = currentURL[:-1].split('/')[-1]
        page = downloadPage(currentURL)
        files = downloadPackage(currentURL, pkgName, page)
        srcFileName = files[1]
        if srcFileName.endswith('/'):
            srcFileName = srcFileName[:-1]
        srcFileName = srcFileName.split('/')[-1]
        makePackage(pkgName, srcFileName)
        installPkg(pkgName)
        os.chdir(workdir)


if __name__ == '__main__':
    if os.getenv('USER') == 'root':
        if len(sys.argv) > 1:
            if sys.argv[1].startswith('-h') or sys.argv[1].startswith('--h'):
                # Help
                ...
            else:
                url = sys.argv[1]
                path = '/' + '/'.join(url.split('/')[3:])
                sequence(path)
        else:
            # About
            ...
    else:
        print('Run it as root.')
