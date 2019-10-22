from setuptools import setup, find_packages

package = "genairics"
version = "0.2.2"

setup(name = package,
      version = version,
      description="GENeric AIRtight omICS pipelines",
      url='https://github.com/beukueb/genairics',
      author = 'Christophe Van Neste',
      author_email = 'christophe.vanneste@ugent.be',
      license = 'GNU GENERAL PUBLIC LICENSE',
      packages = find_packages(),
      install_requires = [
          'luigi',
          'plumbum',
          'xattr',
          'matplotlib',
          'seaborn',
          'pandas',
          'sklearn',
          'requests',
          'argcomplete',
      ],
      extras_require = {
          'interactive_console':  ["ipython"],
          'simulation': ["gffutils"],
          'ChIPseq': ["cutadapt"],
          'wui': ["Flask"]
      },
      package_data = {
          'genairics': [
              'scripts/genairics_dependencies.sh',
              'scripts/buildRSEMindex.sh',
              'scripts/qualitycheck.sh',
              'scripts/simpleDEvoom.R',
              'templates/index.html',
              'static/js/main.js'
          ]
      },
      include_package_data = True,
      zip_safe = False,
      entry_points = {
          'console_scripts': [
              'genairics=genairics.__main__:main',
              'gaxs=genairics.utils:jobserver'
          ],
      },
      test_suite = 'nose.collector',
      tests_require = ['nose']
)

#To install with symlink, so that changes are immediately available:
#pip install -e .
