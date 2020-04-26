#!/usr/bin/env python3

## Copyright 2009-2020 Intel Corporation
## SPDX-License-Identifier: Apache-2.0

import re
import sys
import os
import platform
from glob import glob
import shutil
import tarfile
from zipfile import ZipFile
from urllib.request import urlretrieve
import argparse

ISPC_VERSION = '1.13.0'
TBB_VERSION  = '2020.2'

def run(command):
  if os.system(command) != 0:
    raise Exception('non-zero return value')

def download_file(url, output_dir):
  print('Downloading file:', url)
  filename = os.path.join(output_dir, os.path.basename(url))
  urlretrieve(url, filename=filename)
  return filename

def extract_package(filename, output_dir):
  print('Extracting package:', filename)
  # Detect the package format and open the package
  if re.search(r'(\.tar(\..+)?|tgz)$', filename):
    package = tarfile.open(filename)
    members = package.getnames()
  elif filename.endswith('.zip'):
    package = ZipFile(filename)
    members = package.namelist()
  else:
    raise Exception('unsupported package format')
  # Avoid nesting two top-level directories with the same name
  if os.path.commonpath(members) == os.path.basename(output_dir):
    output_dir = os.path.dirname(output_dir)
  # Create the output directory if it doesn't exist
  if not os.path.isdir(output_dir):
    os.makedirs(output_dir)
  # Extract the package
  package.extractall(output_dir)
  package.close()

def create_package(filename, input_dir):
  print('Creating package:', filename)
  if filename.endswith('.tar.gz'):
    with tarfile.open(filename, "w:gz") as package:
      package.add(input_dir, arcname=os.path.basename(input_dir))
  elif filename.endswith('.zip'):
    shutil.make_archive(filename[:-4], 'zip', os.path.dirname(input_dir), os.path.basename(input_dir))
  else:
    raise Exception('unsupported package format')

def check_symbols(filename, label, max_version):
  with os.popen("nm \"%s\" | tr ' ' '\n' | grep @@%s_" % (filename, label)) as out:
    for line in out:
      symbol = line.strip()
      _, version = symbol.split('@@')
      _, version = version.split('_')
      version = [int(v) for v in version.split('.')]
      if version > list(max_version):
        raise Exception('problematic symbol %s in %s' % (symbol, os.path.basename(filename)))

def check_symbols_linux(filename):
  print('Checking symbols:', filename)
  check_symbols(filename, 'GLIBC',   (2, 17, 0))
  check_symbols(filename, 'GLIBCXX', (3, 4, 19))
  check_symbols(filename, 'CXXABI',  (1, 3, 7))

def main():
  # Detect the OS
  OS = {'Windows' : 'windows', 'Linux' : 'linux', 'Darwin' : 'macos'}[platform.system()]

  # Parse the arguments
  compilers = {'windows' : ['msvc15', 'msvc15-icc18', 'msvc15-icc19', 'msvc15-icc20', 'msvc16', 'msvc16-icc19', 'msvc16-icc20'],
               'linux'   : ['gcc', 'clang', 'icc'],
               'macos'   : ['clang', 'icc']}

  parser = argparse.ArgumentParser()
  parser.usage = '\rIntel(R) Open Image Denoise - Release\n' + parser.format_usage()
  parser.add_argument('stage', type=str, nargs='*', choices=['build', 'package'])
  parser.add_argument('--compiler', type=str, choices=compilers[OS], default=compilers[OS][0])
  parser.add_argument('--config', type=str, choices=['Debug', 'Release', 'RelWithDebInfo'], default='Release')
  parser.add_argument('--wrapper', type=str, help='wrap build command')
  parser.add_argument('-D', dest='cmake_vars', type=str, action='append', help='create or update a CMake cache entry')
  cfg = parser.parse_args()

  # Set the directories
  root_dir = os.environ.get('OIDN_ROOT_DIR')
  if not root_dir:
    root_dir = os.getcwd()
  deps_dir = os.path.join(root_dir, 'deps')
  if not os.path.isdir(deps_dir):
    os.makedirs(deps_dir)
  build_dir = os.path.join(root_dir, 'build_' + cfg.config.lower())

  # Build
  if 'build' in cfg.stage:
    # Set up ISPC
    ispc_release = f'ispc-v{ISPC_VERSION}-'
    ispc_release += {'windows' : 'windows', 'linux' : 'linux', 'macos' : 'macOS'}[OS]
    ispc_dir = os.path.join(deps_dir, ispc_release)
    if not os.path.isdir(ispc_dir):
      # Download and extract ISPC
      ispc_url = f'https://github.com/ispc/ispc/releases/download/v{ISPC_VERSION}/{ispc_release}'
      ispc_url += '.zip' if OS == 'windows' else '.tar.gz'
      ispc_filename = download_file(ispc_url, deps_dir)
      extract_package(ispc_filename, ispc_dir)
      os.remove(ispc_filename)
    ispc_executable = os.path.join(ispc_dir, 'bin', 'ispc')

    # Set up TBB
    tbb_release = f'tbb-{TBB_VERSION}-'
    tbb_release += {'windows' : 'win', 'linux' : 'lin', 'macos' : 'mac'}[OS]
    tbb_dir = os.path.join(deps_dir, tbb_release)
    if not os.path.isdir(tbb_dir):
      # Download and extract TBB
      tbb_url = f'https://github.com/oneapi-src/oneTBB/releases/download/v{TBB_VERSION}/{tbb_release}'
      tbb_url += '.zip' if OS == 'windows' else '.tgz'
      tbb_filename = download_file(tbb_url, deps_dir)
      extract_package(tbb_filename, tbb_dir)
      os.remove(tbb_filename)
    tbb_root = os.path.join(tbb_dir, 'tbb')

    # Create a clean build directory
    if os.path.isdir(build_dir):
      shutil.rmtree(build_dir)
    os.mkdir(build_dir)
    os.chdir(build_dir)

    # Set up common CMake variables
    cmake_vars = f'-D TBB_ROOT="{tbb_root}" '
    if cfg.cmake_vars:
      for var in cfg.cmake_vars:
        cmake_vars += f'-D {var} '

    if OS == 'windows':
      # Set up the compiler
      toolchain = ''
      for compiler in cfg.compiler.split('-'):
        if compiler.startswith('msvc'):
          msvc_version = {'msvc15' : '15 2017', 'msvc16' : '16 2019'}[compiler]
        elif compiler.startswith('icc'):
          icc_version = compiler[3:]
          toolchain = f'Intel C++ Compiler {icc_version}.0'

      # Configure
      run('cmake -L ' +
          f'-G "Visual Studio {msvc_version} Win64" ' +
          f'-T "{toolchain}" ' +
          f'-D ISPC_EXECUTABLE="{ispc_executable}.exe" ' +
          cmake_vars +
          '..')

      # Set up build
      build_cmd = f'cmake --build . --config {cfg.config} --target ALL_BUILD'
    else:
      # Set up the compiler
      cc = cfg.compiler
      cxx = {'gcc' : 'g++', 'clang' : 'clang++', 'icc' : 'icpc'}[cc]
      if cfg.compiler == 'icc':
        icc_dir = os.environ.get('OIDN_ICC_DIR_' + OS.upper())
        if icc_dir:
          cc  = os.path.join(icc_dir, cc)
          cxx = os.path.join(icc_dir, cxx)

      # Configure
      run('cmake -L ' +
          f'-D CMAKE_C_COMPILER:FILEPATH="{cc}" ' +
          f'-D CMAKE_CXX_COMPILER:FILEPATH="{cxx}" ' +
          f'-D CMAKE_BUILD_TYPE={cfg.config} ' +
          f'-D ISPC_EXECUTABLE="{ispc_executable}" ' +
          cmake_vars +
          '..')

      # Set up build
      build_cmd = 'cmake --build . --target preinstall -- -j VERBOSE=1'
    
    # Build
    if cfg.wrapper:
      build_cmd = cfg.wrapper + ' ' + build_cmd
    run(build_cmd)
    
  # Package
  if 'package' in cfg.stage:
    os.chdir(build_dir)

    # Configure
    run('cmake -L -D OIDN_ZIP_MODE=ON ..')

    # Build
    if OS == 'windows':
      run(f'cmake --build . --config {cfg.config} --target PACKAGE')
    else:
      run('cmake --build . --target package -- -j VERBOSE=1')

    # Extract the package
    package_filename = glob(os.path.join(build_dir, 'oidn-*'))[0]
    extract_package(package_filename, build_dir)
    package_dir = re.sub(r'\.(tar(\..*)?|zip)$', '', package_filename)

    # Get the list of binaries
    binaries = glob(os.path.join(package_dir, 'bin', '*'))
    if OS == 'linux':
      binaries += glob(os.path.join(package_dir, 'lib', '*.so*'))
    elif OS == 'macos':
      binaries += glob(os.path.join(package_dir, 'lib', '*.dylib'))
    binaries = list(filter(lambda f: os.path.isfile(f) and not os.path.islink(f), binaries))

    # Check the symbols in the binaries
    if OS == 'linux':
      for filename in binaries:
        check_symbols_linux(filename)

    # Sign the binaries
    sign_file = os.environ.get('OIDN_SIGN_FILE_' + OS.upper())
    if sign_file:
      for filename in binaries:
        run(f'{sign_file} -q -vv {filename}')

      # Repack
      os.remove(package_filename)
      create_package(package_filename, package_dir)

    # Delete the extracted package
    shutil.rmtree(package_dir)

if __name__ == '__main__':
  main()
