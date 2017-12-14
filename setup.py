from setuptools import setup

package = 'genairics'
version = '0.1.2'

setup(name = package,
      version = version,
      description="GENeric AIRtight omICS pipelines",
      url='https://github.com/beukueb/genairics',
      author = 'Christophe Van Neste',
      author_email = 'christophe.vanneste@ugent.be',
      license = 'GNU GENERAL PUBLIC LICENSE',
      packages = ['genairics'],
      install_requires = [
          'luigi',
          'plumbum',
          'matplotlib',
          'pandas',
          'requests',
      ],
      zip_safe = False,
      entry_points = {
          'console_scripts': ['genairics=genairics.__main__:main'],
      },
      test_suite = 'nose.collector',
      tests_require = ['nose']
)

#To install with symlink, so that changes are immediately available:
#pip install -e .
