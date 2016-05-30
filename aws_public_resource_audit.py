#!/usr/bin/python

import boto3
import json
import os
import MySQLdb

os.environ['AWS_ACCESS_KEY_ID'] = "<CHANGEME>"
os.environ['AWS_SECRET_ACCESS_KEY'] = "<CHANGEME>"
os.environ['AWS_DEFAULT_REGION'] = "ap-southeast-2"
os.environ["HTTP_PROXY"] = "http://proxy:3128"
os.environ["HTTPS_PROXY"] = "https://proxy:3128"

final_list = []

conn = MySQLdb.connect(host= "<CHANGEME>",
  user="<CHANGEME>",
  passwd='<CHANGEME>',
  db="<CHANGEME>")

x = conn.cursor()

def sqlCommit(Resource, ResourceType, RecordType, Target):
    try:
	x.execute("INSERT INTO scan_target(Resource, ResourceType, RecordType, Target) VALUES (%s, %s, %s, %s)", (Resource, ResourceType, RecordType, Target))
   	conn.commit()
    except MySQLdb.IntegrityError:
	x.execute("UPDATE scan_target SET LastSuccessfulCheck = NOW() WHERE Resource = %s AND RecordType = %s", (Resource, RecordType))
   	conn.commit()
    except:
	print(x._last_executed)
	raise
	conn.rollback()
#
# Fetching Route53 Entries
#

#print ("Printing route53 entries:\n")

client = boto3.client('route53')

external_zones = client.list_hosted_zones(
    MaxItems='1000'
)

for zone in external_zones['HostedZones']:
    resource_records = client.list_resource_record_sets(
        HostedZoneId=zone['Id'][12:]
    )
    resource_type = "route53"
    for rr in resource_records['ResourceRecordSets']:
        if rr['Type'] == 'A' or rr['Type'] == 'AAAA' or rr['Type'] == 'CNAME':
            if 'ResourceRecords' in rr:
                for val in rr['ResourceRecords']:
		    entry = rr['Name'] + "," + resource_type + "," + rr['Type'] + "," + val['Value']
		    final_list.append(entry)
		    sqlCommit(rr['Name'], resource_type, rr['Type'], val['Value'])
#
# Fetching Public EC2 Entries
#

#print ("Printing Public EC2 instances entries:\n")

client = boto3.client('ec2')
instances_list = []
for region in client.describe_regions()['Regions']:
    ec2 = boto3.resource('ec2',region_name=region['RegionName'])
    instances = ec2.instances.filter(
    Filters=[{'Name': 'instance-state-name','Values': ['running']}])
    for instance in instances:
        if instance.public_ip_address is not None:
            instances_list.append([instance.tags[0]['Value'],instance.public_ip_address])

for instance in sorted(instances_list):
    vm_name = instance[0]
    vm_ip = instance[1]
    resource_type = "ec2"
    record_type = "A"
    entry = vm_name + "," + resource_type + "," + record_type + "," + vm_ip
    final_list.append(entry)
    sqlCommit(vm_name, resource_type, record_type, vm_ip)

#
# Fetching Public ELB Entries
#

#print ("Printing Public ELB entries:\n")

client = boto3.client('elb')
for elb in client.describe_load_balancers()['LoadBalancerDescriptions']:
    if elb['SourceSecurityGroup']['GroupName'] == 'ExtLB':
        elb_name = elb['LoadBalancerName']
        elb_target = elb['DNSName']
    	resource_type = "elb"
    	record_type = "CNAME"
	entry = elb_name + "," + resource_type + "," + record_type + "," + elb_target
    	final_list.append(entry)
    sqlCommit(elb_name, resource_type, record_type, elb_target)

#
# Print contents of the array
#

#print "Resource,ResourceType,RecordType,Target"

#for entry in final_list:
#    print entry

conn.close()

