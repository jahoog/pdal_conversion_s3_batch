import pdal
import json
import os
import sys
import boto3
from pathlib import Path

s3_client = boto3.client("s3")
S3_TARGET_FOLDER = os.environ['S3_TARGET_FOLDER']
S3_TARGET_BUCKET = os.environ['S3_TARGET_BUCKET']
TEMP_FILE_LOCATION = "/tmp"
TRIM_LEADING_FOLDER = True
json_template = {'invocationId': '<a big long string>', 'job': {'id': '<a GUID>'}, 'tasks': [{'taskId': '<a big long string>', 's3BucketArn': 'arn:aws:s3:::<bucket name>', 's3Key': '<s3 key>', 's3VersionId': 'null'}], 'invocationSchemaVersion': '1.0'}

def convert_las_to_copc(input_file, output_file=None):
    """Convert LAS file to COPC format"""
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"ERROR: Input file {input_file} not found")
        return False

    if not input_path.suffix.lower() in ['.las', '.laz']:
        print(f"ERROR: Input file must be .las or .laz format")
        return False

    # Generate output filename if not provided
    if output_file is None:
        output_file = input_path.with_suffix('.copc.laz')

    output_path = Path(output_file)

    print(f"Converting {input_path} to {output_path}")

    # PDAL pipeline for LAS to COPC conversion
    pipeline = {
        "pipeline": [
            str(input_path),
            {
                "type": "writers.copc",
                "filename": str(output_path),
                "forward": "all"
            }
        ]
    }

    try:
        json_pipeline = json.dumps(pipeline)
        pipe = pdal.Pipeline(json_pipeline)
        count = pipe.execute()
        metadata = pipe.metadata
        print(f"Processed {count} points. COPC output: {output_path}")
        print(f"Output file size: {output_path.stat().st_size / (1024*1024):.2f} MB")
        return True
    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        return False
    finally:
        # Clean up temporary pipeline file
        print("Done")

def handler(event, context):
    # Parse job parameters from Amazon S3 batch operations
    invocation_id = event["invocationId"]
    invocation_schema_version = event["invocationSchemaVersion"]

    results = []
    result_code = None
    result_string = None

    task = event["tasks"][0]
    task_id = task["taskId"]
    	    
    # Our source S3 bucket is passed in via the event e.tasks[0].s3BucketArn and e.tasks[0].s3Key (assuming only one task)
    S3_SOURCE_BUCKET=task['s3BucketArn'].split(":::")[-1]
    S3_SOURCE_OBJECT=task['s3Key']

    success = True
    filename = os.path.basename(S3_SOURCE_OBJECT)
    s3_client.download_file(S3_SOURCE_BUCKET, S3_SOURCE_OBJECT, TEMP_FILE_LOCATION + "/" + filename)
    input_file = filename
    output_file = Path(filename).with_suffix('.copc').name
    success = convert_las_to_copc(TEMP_FILE_LOCATION + "/" + input_file, TEMP_FILE_LOCATION + "/" + output_file)

	# create a variable that has just the folder without the filename from S3_SOURCE_OBJECT
    s3_source_folder = "/".join(S3_SOURCE_OBJECT.split("/")[:-1]) + "/"
    s3_target_file = s3_source_folder + output_file
    if TRIM_LEADING_FOLDER:
        s3_target_file = "/".join(s3_target_file.split("/")[1:])

    # Upload the file to the target bucket and folder
    # NOTE: The ExtraArgs is only necessary if the target bucket is in a different account, but should not have an impact if it's the same account
    response = s3_client.upload_file(TEMP_FILE_LOCATION + "/" + output_file, S3_TARGET_BUCKET, S3_TARGET_FOLDER + s3_target_file, ExtraArgs={'ACL':'bucket-owner-full-control'})

    result_code = "Succeeded"
    result_string = (
    	f"Successfully copied converted file "
        f"{S3_TARGET_FOLDER}{s3_target_file} from object {S3_SOURCE_OBJECT}."
    )
    os.remove(TEMP_FILE_LOCATION + "/" + output_file)
    os.remove(TEMP_FILE_LOCATION + "/" + input_file)

    results.append(
    {
    	"taskId": task_id,
        "resultCode": result_code,
        "resultString": result_string,
        }
    )
    
    return {
        "invocationSchemaVersion": invocation_schema_version,
        "treatMissingKeysAs": "PermanentFailure",
        "invocationId": invocation_id,
        "results": results,
    }
