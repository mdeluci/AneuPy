from setuptools import setup, find_packages
def readme():
    with open('README.md') as f:
        return f.read()
setup(
    name='Aneupy',
    version='0.1.0',
    author='Mario de Lucio',
    author_email='mdeluci@purdue.edu',
    description='A Python library for generating simulation-ready geometries of Abdominal Aortic Aneurysms',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/mdeluci/Aneupy',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Medical Science Apps.',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        'numpy',
        'scipy',  # Add any other dependencies your project needs
    ],
    python_requires='>=3.6',
    include_package_data=True,
    zip_safe=False
)
