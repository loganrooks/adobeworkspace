import os
import json
import argparse
from datetime import datetime
import zipfile

from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.exception.exceptions import ServiceApiException, ServiceUsageException, SdkException
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.pdfjobs.result.extract_pdf_result import ExtractPDFResult



import os
import json
import argparse
from datetime import datetime

from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.exception.exceptions import ServiceApiException, ServiceUsageException, SdkException
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.config.client_config import ClientConfig

class ExtractTextInfoFromPDF:
    def __init__(self, input_path, output_dir="output/ExtractTextInfoFromPDF"):
        self.input_path = input_path
        self.output_dir = output_dir
        # Load credentials
        with open('adobe_credentials.json') as f:
            creds = json.load(f)

        credentials = ServicePrincipalCredentials(
            client_id=creds['project']['workspace']['details']['credentials'][0]['oauth_server_to_server']['client_id'],
            client_secret=creds['project']['workspace']['details']['credentials'][0]['oauth_server_to_server']['client_secrets'][0]
        )

        client_config = ClientConfig(read_timeout=60000, connect_timeout=30000)

        pdf_services = PDFServices(credentials=credentials, client_config=client_config)

        try:

            file = open(input_path, 'rb')
            input_stream = file.read()
            file.close()

            # Set up extraction job
            # Creates an asset(s) from source file(s) and upload
            input_asset = pdf_services.upload(input_stream=input_stream, mime_type=PDFServicesMediaType.PDF)
           

            # Create parameters for the job
            extract_pdf_params = ExtractPDFParams(
                elements_to_extract=[ExtractElementType.TEXT],
            )

            # Creates a new job instance
            extract_pdf_job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=extract_pdf_params)

            # Submit the job and gets the job result
            location = pdf_services.submit(extract_pdf_job)
            pdf_services_response = pdf_services.get_job_result(location, ExtractPDFResult)

            # Get content from the resulting asset(s)
            result_asset: CloudAsset = pdf_services_response.get_result().get_resource()
            stream_asset: StreamAsset = pdf_services.get_content(result_asset)

            # Creates an output stream and copy stream asset's content to it
            output_file_path = self.create_output_file_path()
            with open(output_file_path, "wb") as file:
                file.write(stream_asset.get_input_stream())

            print(f"PDF extracted successfully. Results saved to: {output_file_path}")


            archive = zipfile.ZipFile(output_file_path, 'r')
            jsonentry = archive.open('structuredData.json')
            jsondata = jsonentry.read()
            data = json.loads(jsondata)

            # Text processing will be handled by the conversion script
            # for element in data["elements"]:
            #     if element["Path"].endswith("/H1"):
            #         print(element["Text"])

        except (ServiceApiException, ServiceUsageException, SdkException) as e:
            print(f"Error during PDF extraction: {str(e)}")
            raise

    def create_output_file_path(self):
        # Use the base name of the input PDF for the zip file
        input_filename = os.path.basename(self.input_path)
        base_name, _ = os.path.splitext(input_filename)
        output_filename = f"{base_name}.zip"
        os.makedirs(self.output_dir, exist_ok=True)
        return os.path.join(self.output_dir, output_filename)
    

def main():
    parser = argparse.ArgumentParser(description='Extract text and headers from PDF using Adobe API')
    parser.add_argument('input_pdf', help='Path to input PDF file')
    parser.add_argument('--output_dir', '-o', default='output/ExtractTextInfoFromPDF', help='Directory to save the output ZIP file')
    args = parser.parse_args()

    if not os.path.exists(args.input_pdf):
        raise FileNotFoundError(f"Input PDF not found: {args.input_pdf}")

    # Pass output_dir to the class
    ExtractTextInfoFromPDF(args.input_pdf, args.output_dir)

if __name__ == '__main__':
    main()