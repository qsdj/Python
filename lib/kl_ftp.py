# -*- coding: utf-8 -*-
'''
+----------------------------------------------------------------------
// | Author: 赵克立 <735579768@qq.com> <http://www.zhaokeli.com>
// |mysql数据库操作类
+----------------------------------------------------------------------
// |远程和本地目录以不要 "/" 结尾
'''
import ftplib, os , kl_log, paramiko, threading, math, time
#定义匿名函数
#打开一个文件句柄
writeFile = lambda filename:open(filename, 'wb').write
#创建目录
createDir = lambda dirname: not os.path.exists(dirname) and os.makedirs(dirname)

class kl_ftp:
    def __init__(self,host,port,username,password):
        self.host=host
        self.port=port
        self.username=username
        self.password=password
        self.downloading=0
        self.bigfile=[]
        self.ftp = None
        self.ignorefolder=[]
        self.faillist=[]
        self.localroot='./'
        self.ftp=self.__ftpconn()
        #初始化日志
        self.log=kl_log.kl_log('kl_ftp')

    def __ftpconn(self):
        ftp=ftplib.FTP()
        #最大1G文件
        ftp.maxline=1024*1024*1024
        #f.encoding='UTF-8'#防止中文乱码
        ftp.connect(self.host,self.port)
        resp = ftp.login(self.username, self.password)
        #输出欢迎信息
        #print(resp)
        return ftp

    #判断是否是目录
    def isDirectory(self,filename):
        try:
            self.ftp.cwd(filename)
            createDir(self.localroot+filename)
            return True
        except ftplib.error_perm as e:
            #如果不是目录会报错并返回False
            #print(e)
            return False

    #下载ftp文件
    def __recursiveDownload(self,filelist, curpwd):
        for file in filelist:
            if file != '.' and file != '..' :
                if file in self.ignorefolder:
                    continue
                fol=curpwd + file
                try:
                    if self.isDirectory(fol):
                        self.__recursiveDownload(self.ftp.nlst(), self.ftp.pwd())
                    else:
                        localpath=self.localroot + fol
                        print('downloading...%s ----> %s'%(fol, localpath))

                        #取文件的大小
                        cmd = "SIZE "+fol
                        ret = self.ftp.sendcmd(cmd)
                        fsize = int(ret.split(' ')[1])
                        #大于10M的文件用多线程分块下载
                        if fsize>1024*1024*10:
                            self.bigfile.append(fol)
                            print('downloading...%s ----> %s'%(fol, localpath))
                            print('start treading download file: size %d M'%(fsize/(1024*1024)))
                            #self.download_by_thread(fol,fsize,10)
                            threading.Thread(target=self.download_by_thread, args=(fol,fsize, 5,)).start()
                        else:
                            self.ftp.retrbinary('RETR '+fol, writeFile(localpath),self.ftp.maxline)
                except Exception as e:
                    print(e)
                    self.faillist.append(fol)
                    self.log.write("Error:%s"%e)
                    self.log.write("%s"%e)


    #从远程下载单个文件到本地
    def downloadfile(self,filepath,localpath):
        self.localroot=localpath
        onlydir = os.path.dirname(filepath)
        onlyname = os.path.basename(filepath)
        self.ftp.cwd(onlydir)
        createDir(self.localroot+'/'+onlydir)
        self.__recursiveDownload([onlyname], self.ftp.pwd());
        self.__isdownloadover()
        return True

    #下载远程文件夹到本地
    def downloadfolder(self,folder,localroot):
        if self.ftp:
            self.localroot=localroot
            self.ftp.cwd(folder)
            createDir(self.localroot+'/'+folder)
            self.__recursiveDownload(self.ftp.nlst(), self.ftp.pwd());
        self.log.write("下载错误的文件:%s"%self.faillist)
        print('下载错误的文件:')
        print(self.faillist)
        self.__isdownloadover()
        return True

    #判断是否下载完成
    def __isdownloadover(self):
        print('大文件正在下载...%s'%self.bigfile)
        while self.downloading!=0:
            time.sleep(1)
        print('下载完成!')

    #从本地上传文件到远程
    def uploadfile(self,localpath,remotepath):
        onlydir=os.path.dirname(remotepath)
        self.__mkdremote(onlydir)
        if not os.path.isfile(localpath):
            return
        print ('+++ upload %s to %s:%s'%(localpath, self.host, remotepath))
        self.ftp.storbinary('STOR ' + remotepath, open(localpath, 'rb'))

    #创建远程目录路径
    def __mkdremote(self,dirpath):
        arr=dirpath[1:].split('/')
        mdir=''
        for i in arr:
            if i!='':
                try:
                    mdir+='/'+i
                    self.ftp.mkd(mdir)
                except:
                    pass
                #self.ftp.cwd(i)

    #上传本地文件夹到远程
    def uploadfolder(self,localdir,remotedir):
        if not os.path.isdir(localdir):
            return
        #self.__mkdremote(remotedir)
        #self.ftp.cwd(remotedir)
        for file in os.listdir(localdir):
            src=localdir+'/'+file
            if os.path.isfile(src):
                self.uploadfile(src, remotedir+'/'+file)
            elif os.path.isdir(src):
                self.uploadfolder(src, remotedir+'/'+file)

    def close(self):
        if self.ftp!=None:
            self.ftp.quit()

    def download_by_thread(self, filename,fsize, threadnum=1, blocksize=8192):
        self.downloading=self.downloading+1
        print ('file', filename, 'size:', fsize)
        rest = None
        bsize = math.ceil(fsize / threadnum)

        # 创建线程
        threads= []
        for i in range(0, threadnum-1):
            begin = bsize * i
            print (i, begin, bsize)
            tp = threading.Thread(target=self.download_file, args=(i, filename,begin,bsize,blocksize,rest,))
            threads.append(tp)

        #计算最后一个线程下载剩下的全部大小
        have1 = bsize * threadnum
        have2 = fsize - have1
        lastsize = bsize + have2
        begin = bsize * (threadnum-1)
        print (threadnum-1, begin, lastsize)
        tp = threading.Thread(target=self.download_file, args=(threadnum-1, filename, begin,lastsize,blocksize,rest,))
        threads.append(tp)

        print ('threads:', len(threads))

        #启动下载线程
        for t in threads:
            t.start()
            time.sleep(1)
        #阻塞线程下载,直到结束
        for t in threads:
            t.join()

        # 每个线程都下载完成了，合并临时文件为一个文件
        fw = open(self.localroot+filename, "wb")
        for i in range(0, threadnum):
         fname =self.localroot+ filename+'.part.'+str(i)
         print (fname)
         if not os.path.isfile(fname):
            print ('not found', fname)
            continue
         f1 = open(fname, 'rb')
         while 1:
            data = f1.read(8192)
            if not len(data):
                   break
            fw.write(data)
         f1.close()
         os.remove(fname)
        fw.close()
        print ('all ok')
        self.bigfile.remove(filename)
        self.downloading=self.downloading-1

    def download_file(self, inx, filename, begin=0, size=0, blocksize=8192, rest=None):
        onlydir = os.path.dirname(filename)
        onlyname = os.path.basename(filename)
        tname = threading.currentThread().getName()+': '
        # 新建一个连接来下载，每个线程一个连接，注意这里没有考虑有些ftp服务器限制一个ip只能有多少连接的情况。
        myftp=None
        try:
            myftp =self.__ftpconn()
        except Exception as e:
            return False
        myftp.cwd(onlydir)
        #print('进入文件夹:%s'%onlydir)
        # 创建临时文件
        fp = open(self.localroot+filename+'.part.'+str(inx), 'wb')
        #fp.seek(begin)

        callback = fp.write

        haveread = 0
        myftp.voidcmd('TYPE I')
        # 告诉服务器要从文件的哪个位置开始下载
        cmd1 = "REST "+str(begin)
        print ('%s : 下载文件位置--> %s'%(tname, cmd1))
        ret = myftp.sendcmd(cmd1)
        # 开始下载
        cmd = "RETR "+onlyname
        conn = myftp.transfercmd(cmd, rest)
        readsize = blocksize
        while 1:
         if size > 0:
            last = size - haveread
            if last > blocksize:
                   readsize = blocksize
            else:
                   readsize = last
         data = conn.recv(readsize)
         if not data:
            break

         # 已经下载的数据长度
         haveread = haveread + len(data)
         # 只能下载指定长度的数据，下载到就退出
         if haveread > size:
            print (tname, 'haveread:', haveread, 'size:', size)
            hs = haveread - size
            callback(data[:hs])
            break
         elif haveread == size:
            callback(data)
            print (tname, 'haveread:', haveread)
            break

         callback(data)

        conn.close()
        fp.close()
        try:
            ret = myftp.getresp()
        except Exception as e:
            pass
            #print ('%s %s'%(tname,e))
        myftp.quit()
        #print('返回值是:%s'%ret)
        return ret

class kl_sftp:
    def __init__(self,host,port,username,password):
        self.ssh=None
        self.sftp=None
        self.ignorefolder=[]
        self.faillist=[]
        self.localroot='./'
        self.__sftpconn(host,username,password)
        #初始化日志
        self.log=kl_log.kl_log('kl_sftp')

    #定义 ssh 连接函数
    def __sftpconn(self,_host,_username='',_password=''):
        try:
            self.ssh= paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy( paramiko.AutoAddPolicy() )
            self.ssh.connect(_host,username=_username,password=_password)
            self.sftp=self.ssh.open_sftp()
            self.sftp.chdir('/')
            print('当前目录:%s'%self.sftp.getcwd())
        except Exception as e:
            print( 'ssh %s@%s: %s' % (_username,_host, e) )
            exit()

    #判断是否是目录
    def isDirectory(self,filename):
        try:
            self.sftp.chdir(filename)
            createDir(self.localroot+filename)
            return True
        except Exception as e:
            #如果不是目录会报错并返回False
            #print(e)
            return False

    #从远程下载单个文件到本地
    def downloadfile(self,filepath,localpath):
        onlydir = os.path.dirname(filepath)
        onlyname = os.path.basename(filepath)
        if self.sftp:
            self.localroot=localpath
            self.sftp.chdir(onlydir)
            createDir(self.localroot+onlydir)
            self.__downfilelist([onlyname], self.sftp.getcwd());
        self.log.write("下载错误的文件:%s"%self.faillist)
        print('下载错误的文件:')
        print(self.faillist)
        return True

    #从本地上传文件到远程
    def uploadfile(self,localpath,remotepath):
        pass

    #上传本地文件夹到远程
    def uploadfolder(self,localroot,folder):
        pass
    def __downfilelist(self,filelist, curpwd):
        for file in filelist:
             if file != '.' and file != '..' :
                if file in self.ignorefolder:
                    continue
                fol=curpwd +'/'+ file
                try:
                    if self.isDirectory(fol):
                        self.__downfilelist(self.sftp.listdir(), self.sftp.getcwd())
                    else:
                        localpath=self.localroot+fol
                        print('downloading...%s ----> %s'%(fol, localpath))
                        self.sftp.get(fol,localpath)
                except Exception as e:
                    print(e)
                    self.faillist.append(fol)
                    self.log.write("Error:%s"%e)
                    self.log.write("%s"%e)


    def downloadfolder(self,folder,localroot):
        if self.sftp:
            self.localroot=localroot
            self.sftp.chdir(folder)
            createDir(self.localroot+folder)
            self.__downfilelist(self.sftp.listdir(), self.sftp.getcwd());
        self.log.write("下载错误的文件:%s"%self.faillist)
        print('下载错误的文件:')
        print(self.faillist)
        return True

    def ssh_command(self,command):
        stdin, stdout, stderr = self.ssh.exec_command(command)
        relist=[]
        for i in stdout.readlines():
            relist.append(i.strip('\n'))
        print(relist)

    def close(self):
        if self.sftp!=None:
            self.sftp.close()
        if self.ssh!=None:
            self.ssh.close()


if __name__ == '__main__':
    # print('请输入用户名:')
    # username=input()
    # print('请输入密码:')
    # password=input()

    #连接ftp服务器
    ftp=kl_ftp('192.168.198.131',2016,'wwwroot','123456')
    ftp.ignorefolder=['Data', 'Public', 'App', 'Plugins', 'TP']
    #ftp.downloadfile('test/dflz.zip','E:/ftp')
    #ftp.downloadfolder('test','E:/ftp')

    #上传文件
    #ftp.uploadfile('E:/ftp/test/dflz.zip', '/new/dflz.org/dflz.zip')
    #上传文件夹
    ftp.uploadfolder('E:/ftp/test', '/news')
    ftp.close()

    #连接ssh服务器
    # sftp=kl_sftp('116.255.159.47', 22,'root', password)
    # sftp.ignorefolder=['Data', 'Public', 'App', 'Plugins', 'TP','zhaokeli.com.zip']
    # sftp.downloadfolder('/var/www/zhaokeli.com', 'E:/sftp')
    # sftp.close()
    input('请输入任意键结束...')
