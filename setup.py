from setuptools import setup, find_packages

setup(
    name='django-http-readonly-storage',
    version='0.0.1',
    description='HTTP read-only storage backend for Django',
    author='Andrew Perry',
    author_email='ajperry@pansapiens.com',
    url='http://github.com/pansapiens/django-http-readonly-storage',
    keywords=['django', 'storage'],
    packages = find_packages(exclude=['tests.*']),
    zip_safe=False,
    classifiers = [
        'Environment :: Web Environment',
        'Framework :: Django',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    requires = [
        'django',
        'requests (>=2.0)',
    ],
)
