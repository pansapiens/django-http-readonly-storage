from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import ast
from pathlib2 import Path
import cgi
from urlparse import urlparse, urljoin
import io
from io import BytesIO
from django.core.files.storage import Storage as StorageBase
from django.core.files.base import File
import requests


class HTTPReadOnlyStorage(StorageBase):
    """
    A read-only HTTP endpoint storage backend.
    """

    def __init__(self, **kwargs):
        """
        Keyword args:
        'location' - a common URL to prefix to all filenames under this backend
                     (eg https://example.com/ ). The default is an empty string,
                     allowing 'filenames' to be full URLs to anywhere.

        'stream' - if True, content will be streamed (more memory efficient).
                   If False, a downloaded file is held in memory while in use.

        'chunk_size' - the chunk size to hold in memory when streaming. This
                       corresponds to the `requests` `iter_content(chunk_size)`

        :param kwargs: Backend options
        :type kwargs: dict
        """
        #
        # self.session = self.get_requests_instance(**kwargs)

        self.url_base = kwargs.get('location', '')
        self.stream = kwargs.get('stream', True)
        if isinstance(self.stream, basestring):
            self.stream = ast.literal_eval(self.stream)

        self.chunk_size = kwargs.get('chunk_size', str(File.DEFAULT_CHUNK_SIZE))
        if isinstance(self.chunk_size, basestring):
            self.chunk_size = ast.literal_eval(self.chunk_size)

    def listdir(self, path):
        raise NotImplementedError()

    # def get_requests_instance(self, **kwargs):
    #     return requests.Session()

    def http(self, method, name, *args, **kwargs):
        url = self.get_download_url(name)
        method = method.lower()
        # response = getattr(self.session, method)(url, *args, **kwargs)
        response = requests.request(method, url, *args, **kwargs)
        response.raise_for_status()
        return response

    def get_download_url(self, name):
        parsed = urlparse(name)
        if parsed.scheme:
            return name
        return urljoin(self.url_base, name)

    def _open(self, name, mode='rb'):
        url = self.get_download_url(name)
        remote_file = HTTPReadOnlyStorageFile(name, url, self,
                                              stream=self.stream,
                                              chunk_size=self.chunk_size)
        return remote_file

    def _read(self, name):
        return self._open(name).read()

    def _save(self, name, content):
        raise NotImplementedError()

    def delete(self, name):
        raise NotImplementedError()

    def exists(self, name):
        try:
            self.http('HEAD', name)
        except requests.exceptions.HTTPError:
            return False
        else:
            return True

    def size(self, url):
        """
        Tries to determine the file size for a given download URL via the
        Content-Length header.

        :param url: The URL
        :type url: str
        :return: The file/download size in bytes
        :rtype: int
        """
        try:
            return int(self.http('HEAD', url).headers['Content-Length'])
        except (KeyError, ValueError, requests.exceptions.HTTPError):
            raise IOError('Unable get size for %s' % url)

    def _filename_from_url(self, url):
        """
        Tries to determine the filename for a given download URL via the
        Content-Disposition header - falls back to path splitting if that header
        isn't present, and raises a ValueError if it can't be determined
        via path splitting.

        :param url: The URL
        :type url: str
        :return: The download filename
        :rtype: str
        """
        filename = None
        head = self.http('HEAD', url)
        filename_header = cgi.parse_header(
            head.headers.get('Content-Disposition', ''))[-1]
        if 'filename' in filename_header:
            filename = filename_header.get('filename').strip()
        else:
            filename = str(Path(urlparse(url).path).name)

        if not filename:
            raise ValueError('Could not find a filename for: %s' % url)

        return filename

    def url(self, name):
        return self.get_download_url(name)

    def get_base_url(self):
        return self.url('').rstrip('/')


class HTTPReadOnlyStorageFile(File):
    """
    Represents an HTTP URL as a read-only file-like object.

    """
    def __init__(self, name, url, storage, stream=True, chunk_size=None):
        self.name = name
        self.url = url
        self._storage = storage
        self.mode = 'rb'
        self.stream = stream
        self._response = None
        self._content = None
        self._file = None
        self._chunk_size = chunk_size
        if chunk_size is None:
            self._chunk_size = self.DEFAULT_CHUNK_SIZE

        self._open()

    @property
    def file(self):
        if not self._response:
            self._open()
        return self._response.raw

    @property
    def size(self):
        if not hasattr(self, '_size'):
            if not self.stream and self._file:
                self._open()
                self._size = len(self._file.read())
            else:
                self._size = self._storage.size(self.name)
        return self._size

    def readlines(self):
        if self.stream:
            return self._response.iter_lines()
        else:
            return str(self._file.read()).split()

    def _open(self):
        self.close()
        # We make HTTP requests via a method on the Storage object,
        # since this potetially allows the Storage object to inject
        # authentication headers etc
        self._response = self._storage.http('GET', self.name,
                                            stream=self.stream)
        if self.stream:
            self._content = self._response.iter_content(
                chunk_size=self._chunk_size)
        else:
            self._file = BytesIO(self._response.content)

        return self

    def read(self, num_bytes=2**16):
        if self.stream:
            data = self._content.next()
        else:
            data = self._file.read(num_bytes)
        return data

    # def chunks(self, chunk_size=File.DEFAULT_CHUNK_SIZE):
    #     self._chunk_size = chunk_size
    #     if not self._request:
    #         self._open()
    #     return self._content

    def write(self, content):
        raise NotImplementedError()

    def close(self):
        if self._response:
            self._response.close()
