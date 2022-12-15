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
    downloadURL = url.split('\\')
    for index, srcURL in enumerate(downloadURL):
        downloadURL[index] = downloadURL[index].replace(' ', '')
        downloadURL[index] = downloadURL[index].replace('\n', '')

    files = []
    for file in downloadURL:
        print(file)
        files += [wget.download(file)]

    return files.copy()


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

    srcURLStart, srcURL, srcURLEnd, srcURL = 0, '', 0, ''
    cpuArch = os.popen('uname -m').read()[:-1]

    if (f'DOWNLOAD_{cpuArch}' in info) and \
            (f'DOWNLOAD_{cpuArch}=\"\"' not in info) and \
            (f'DOWNLOAD_{cpuArch}=\" \"' not in info):
        key = f'DOWNLOAD_{cpuArch}=\"'
        srcURLStart = info.index(key) + len(key)
        srcURL = info[srcURLStart:]
        srcURLEnd = srcURL.index('\"')
        srcURL = srcURL[:srcURLEnd]
    else:
        srcURLStart = info.index('DOWNLOAD=\"') + 10
        srcURL = info[srcURLStart:]
        srcURLEnd = srcURL.index('\"')
        srcURL = srcURL[:srcURLEnd]

    if not os.path.exists(name):
        os.mkdir(name)
    os.chdir(name)
    print(f'Downloading {sbURL}...')
    sbFilename = downloadFile(sbURL)[0]
    print(f'Downloading {srcURL}...')
    srcFilenames = downloadFile(srcURL)
    os.chdir('..')

    return sbFilename, srcFilenames


def makePackage(name, srcFilenames):
    os.chdir(name)

    tar = tarfile.open(f'{name}.tar.gz', 'r:gz')
    tar.extractall()
    tar.close()

    for srcFilename in srcFilenames:
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
    VERSION = VERSION[VERSION.index('-')+1:VERSION.index('}')]

    if 'ARCH=noarch' not in slackBuild:
        ARCH = os.popen('uname -m').read()[:-1]
    else:
        ARCH = 'noarch'

    buildStartIndex = slackBuild.index('BUILD=$')
    buildEndIndex = slackBuild[buildStartIndex:].index('\n')
    BUILD = slackBuild[buildStartIndex+7:buildStartIndex+buildEndIndex]
    print(BUILD)
    BUILD = BUILD[BUILD.index('-')+1:BUILD.index('}')]

    tagStartIndex = slackBuild.index('TAG=')
    tagEndIndex = slackBuild[tagStartIndex:].index('\n')
    TAG = slackBuild[tagStartIndex+4:tagStartIndex+tagEndIndex]
    TAG = TAG[TAG.index('-')+1:TAG.index('}')]

    typeStartIndex = slackBuild.index('PKGTYPE=')
    typeEndIndex = slackBuild[typeStartIndex:].index('\n')
    PKGTYPE = slackBuild[typeStartIndex+8:typeStartIndex+typeEndIndex]
    PKGTYPE = PKGTYPE[PKGTYPE.index('-')+1:PKGTYPE.index('}')]

    pkgPath = f'/tmp/{PRGNAM}-{VERSION}-{ARCH}-{BUILD}{TAG}.{PKGTYPE}'
    print(pkgPath)
    os.chdir('/tmp')
    os.system(f'upgradepkg --install-new {pkgPath}')


def queuePkgs(pkgURL, queue):
    queue.append(pkgURL)
    page = f'http://slackbuilds.org/{pkgURL}'
    deps = listDependencies(downloadPage(page))
    if deps != -1:
        for dep in deps:
            #if dep not in queue:
            queuePkgs(dep, queue)
            #else:
            #    print('!! WARNING !! Cycle dependency found!')
            #    pkgName = pkgURL[:-1].split('/')[-1]
            #    depName = dep[:-1].split('/')[-1]
            #    print(f'{pkgName} -> {depName}')
            #    exit(1)
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
        srcFileNames = files[1]
        makePackage(pkgName, srcFileNames)
        installPkg(pkgName)
        os.chdir(workdir)


if __name__ == '__main__':
    if os.getenv('USER') == 'root':
        if len(sys.argv) > 1:
            if sys.argv[1].startswith('-h') or sys.argv[1].startswith('--h'):
                # Help
                print(f'\nUsage: {sys.argv[0]} [sbolink]')
            else:
                url = sys.argv[1]
                if not url.endswith('/'):
                    url += '/'
                path = '/' + '/'.join(url.split('/')[3:])
                sequence(path)
        else:
            # About
            print('sbomgr - SlackBuilds.Org Manager')
            print('v. 0.1')
            print('thm, 2022')
            print('https://github.com/thm-unix/sbomgr/')

            print()
            print('sbomgr is a simple utility that can install packages (and resolve their dependencies) from '
                  'slackbuilds.org.'
                  '\nPlease note that you should check out README of package, if something does not work.'
                  f'\nUsage: {sys.argv[0]} [sbolink]')
    else:
        print('Run it as root.')
