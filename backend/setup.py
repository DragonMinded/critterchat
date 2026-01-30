from setuptools import setup


setup(
    name='critterchat',
    version='0.0.58',
    description='CritterChat self-hosted web chat software.',
    author='DragonMinded',
    license='Public Domain',
    packages=[
        'critterchat',
        'critterchat.common',
        'critterchat.config',
        'critterchat.data',
        'critterchat.data.migrations',
        'critterchat.data.migrations.versions',
        'critterchat.http',
        'critterchat.http.static',
        'critterchat.http.templates',
        'critterchat.manage',
        'critterchat.service',
    ],
    install_requires=[
        req for req in open('requirements.txt').read().split('\n') if len(req) > 0
    ],
    include_package_data=True,
)
