from setuptools import find_packages, setup

setup(
    name='netbox-swim',
    version='0.1.0',
    description='A modular Software Image Management (SWIM) system for NetBox',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'scrapli',
        'netmiko',
        'ntc_templates',
        'pyats',
        'unicon',
        'genie'
    ],
)
