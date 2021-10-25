import urllib.request
import urllib.error
import urllib.parse
import os
import time


def DownloadURL(url, file_name=None, overwrite=False):
    """Download File in URL"""
    curpath = os.path.abspath(os.curdir)
    if file_name is None:
        file_name = url.split('/')[-1]
    try:
        u = urllib.request.urlopen(url)
    except Exception:
        return
    if os.path.exists(file_name) and not overwrite:
        print("Rakitra efa misy! Tsy navela nanitsaka")
        return

    print("Trying to open: %s" % (os.path.join(curpath, file_name)))
    f = open(file_name, 'wb')
    meta = u.info()
    file_size = int(meta.getheaders("Content-Length")[0])
    # print "Loharano : %s \nTanjona : %s\nLanja : %.1f Kio" % (url,
    # file_name, file_size/1024.)

    file_size_dl = 0
    block_sz = 32768
    o_file_size_dl = 0
    dl_spd = 0
    timer = time.time()
    chrono = .1
    while file_size_dl < file_size:
        buff = u.read(block_sz)
        if not buff:
            break

        file_size_dl += len(buff)

        f.write(buff)
        chrono = time.time() - timer
        if chrono != 0.:
            dl_spd = (
                (((file_size_dl - o_file_size_dl) / 1024.) / chrono) + dl_spd) / 2
        status = r"%d kB [%3.0f%%, %.1f kB/s]" % (
            file_size_dl / 1024., file_size_dl * 100. / file_size, dl_spd)
        o_file_size_dl = file_size_dl
        status = status + chr(8) * (len(status) + 1)
        timer = time.time()
        print(status, end=' ')

    print("Vita ny asa amin'i %s" % file_name)
    f.close()


if __name__ == '__main__':
    import time

    volana = [
        '',
        'jan',
        'feb',
        'mar',
        'apr',
        'mey',
        'jon',
        'jol',
        'aog',
        'sep',
        'okt',
        'nov',
        'des']
    t = []
    t = list(time.gmtime())
    e = "%d/%d/%d -- %d:%2d:%2d" % (t[2], t[1], t[0], t[3], t[4], t[5])
    e += (1 + len(e)) * chr(8)
    print(e)
