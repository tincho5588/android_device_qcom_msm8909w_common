#! /usr/bin/python

#
# Copyright (c) 2016, The Linux Foundation. All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of The Linux Foundation nor
#        the names of its contributors may be used to endorse or promote
#        products derived from this software without specific prior written
#        permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NON-INFRINGEMENT ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
#  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
#  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
#  WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
#  OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#  ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#


# This script generates single bootloader image from the following images
# sbl1, modem, rpm, tz, and emmc_appsboot
#
# It is assumed that this script is run from root of meta build.
# The script automatically detects the individual image paths
# (that are part of the meta build) and generates the single
# bootloader image.
#
# Note: This script is sensitive to changes in meta format that is
# part of Little Kernel (lk).
#
# Current implementation is tightly coupled with below definition.
#
#    #define META_HEADER_MAGIC  0xce1ad63c
#    #define MAX_GPT_NAME_SIZE  72
#    typedef unsigned int u32;
#    typedef unsigned short int u16;
#
#    typedef struct meta_header {
#      u32       magic;                  /* 0xce1ad63c */
#      u16       major_version;      /* (0x1) - reject images with higher major versions */
#      u16       minor_version;      /* (0x0) - allow images with higer minor versions */
#      char      img_version[64]; /* Top level version for images in this meta */
#      u16       meta_hdr_sz;    /* size of this header */
#      u16       img_hdr_sz;     /* size of img_header_entry list */
#    } meta_header_t;
#
#    typedef struct img_header_entry {
#      char      ptn_name[MAX_GPT_NAME_SIZE];
#      u32       start_offset;
#      u32       size;
#    } img_header_entry_t;
#
# For further details please refer to meta_image tool that is part of APSS build.
#

import sys
import os
import subprocess
import pprint
from ctypes import *
import struct
from optparse import OptionParser


options_version = ""

import os,sys
temp_param_holder = ""
temp_image_name = ""
image_name_list = {}
partition_name_map = {}

# Get the arguments list
input_cmdargs = []
input_cmdargs.append("dummy")
input_cmdargs += sys.argv[1].split()

for i in range(1,len(input_cmdargs)):
	if input_cmdargs[i] == "-v" :
		options_version = input_cmdargs[i+1]
		print "=========options_version:"+ options_version + "\n"
		break
	if i%2 : # Odd argument is partition name,
		temp_param_holder = input_cmdargs[i]
		continue
	temp_image_name = temp_param_holder
	if(temp_param_holder=="aboot") :
		temp_image_name='apps'
	if(temp_param_holder=="sbl1") :
		temp_image_name='boot'
	image_name_list[temp_image_name]=input_cmdargs[i]
	partition_name_map[temp_image_name]=temp_param_holder


image_info_list = []

#defines
META_HEADER_MAGIC = 0xce1ad63c
MAX_GPT_NAME_SIZE = 72
META_IMAGE_VERSION_SIZE = 64
META_HEADER_SIZE = 76
IMAGE_HEADER_SIZE = 80

#offset of first image in the bootloader.img
offset = META_HEADER_SIZE + IMAGE_HEADER_SIZE*len(image_name_list) #sizeof meta_header + img_header


class ImageHeader(object):
	def __init__(self,ptn_name, start_offset, size, file):
		self._ptn_name = ptn_name
		self._start_offset = start_offset
		self._size = size
		self._file = file

	@property
	def ptn_name(self):
		return self._ptn_name

	@property
	def start_offset(self):
		return self._start_offset

	@property
	def size(self):
		return self._size

	@property
	def file(self):
		return self._file

for image_name, image_rel_path in image_name_list.iteritems():
	#print image_name
	#print image_rel_path
	image_path = image_name_list[image_name]
	try:
		#print "image_name: ", image_name, " image_path: ", image_path ,"partition_name_map[image_name]:",partition_name_map[image_name] ,"\n"
		file = open(image_path, "rb")
		info = os.stat(image_path)
		#print info
		header = ImageHeader(partition_name_map[image_name], offset, info.st_size, file)
		offset += info.st_size
		#pp = pprint.PrettyPrinter(indent=4)
		#pp.pprint(header)
		image_info_list.append(header)
		#pp.pprint(image_info_list)
	except IOError as e:
		print str(e)
		print "Failed to open " + image_path
	except:
		print "Unknown Error"
		exit()

try:
	f_bootloader = open("bootloader.img", "wb")

	#write the meta header
	f_bootloader.write(struct.pack('<I', META_HEADER_MAGIC))
	f_bootloader.write(struct.pack('<H', 1))
	f_bootloader.write(struct.pack('<H', 0))
	print "version " + options_version
	length = len(options_version)
	length = META_IMAGE_VERSION_SIZE-length
	if length <= 0:
		length = 0
	f_bootloader.write(options_version)
	for i in range(0,length):
		f_bootloader.write(struct.pack('<c', '\0'))
	f_bootloader.write(struct.pack('<H', META_HEADER_SIZE))
	f_bootloader.write(struct.pack('<H', IMAGE_HEADER_SIZE*len(image_name_list)))

	#write the image header
	print "Generation single bootloader image with:"
	print "     Partition\t\toffset\t\tsize"
	for image_info in image_info_list:
		print "-->  %s\t\t%s\t\t%s" %(image_info.ptn_name, image_info.start_offset, image_info.size)
		length = len(image_info.ptn_name)
		length = MAX_GPT_NAME_SIZE-length
		if length <= 0:
			length = 0
		f_bootloader.write(image_info.ptn_name)
		for i in range(0,length):
			f_bootloader.write(struct.pack('<c', '\0'))
		f_bootloader.write(struct.pack('<I', image_info.start_offset))
		f_bootloader.write(struct.pack('<I', image_info.size))

	#Now write the actual images
	for image_info in image_info_list:
		f_bootloader.write(image_info.file.read())
	f_bootloader.close()
except IOError as e:
	print str(e)
except:
	print "Unknown Error"

