from common import *



# *************************************************************
# *************************************************************
# S3 operations 
# *************************************************************
# *************************************************************

def download_files_from_s3(cluster_id):
    bucket_name = 'asuplogs'    
    local_base_dir = 'data'

    # Initialize the S3 client
    s3 = boto3.resource(
        service_name='s3',
        region_name='us-east-1',        
    )
    
    # Define the S3 folder and local folder paths
    s3_folder = f"{cluster_id}/"
    local_directory = os.path.join(local_base_dir, cluster_id)

    # Create the local base directory for the cluster if it doesn't exist
    os.makedirs(local_directory, exist_ok=True)   

    # Get all objects from the specified S3 folder
    bucket = s3.Bucket(bucket_name)
    objects = bucket.objects.filter(Prefix=s3_folder)

    for obj in objects:
        # Remove the folder name (cluster ID) from the S3 key to get the relative path
        relative_path = obj.key[len(s3_folder):]

        # Skip empty folder keys (i.e., paths ending with a "/")
        if not relative_path:
            continue

        # Create the local path for the file (preserving subfolders)
        local_file_path = os.path.join(local_directory, relative_path)

        # Ensure any intermediate directories are created
        if '/' in relative_path:
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        # Download the file
        print(f"Downloading {obj.key} to {local_file_path}...")
        bucket.download_file(obj.key, local_file_path)

    print(f"All files from {cluster_id} have been downloaded to {local_directory}.")
