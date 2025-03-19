# **Documentation for Adobe PDF Services API Python Implementation**

## **1\. Introduction to Adobe PDF Services API Python SDK**

The Adobe PDF Services API represents a suite of cloud-based functionalities designed to enable developers to programmatically interact with PDF documents 1. This API offers a wide array of capabilities, including the creation, conversion, combination, securing, and extraction of content from PDF files 1. Beyond these fundamental operations, the API also provides access to more advanced services such as Document Generation and PDF Extract, empowering sophisticated document workflows 5. The accessibility of these services through Software Development Kits (SDKs) for various programming languages, including Python, facilitates seamless integration into diverse application environments 1. This comprehensive toolset positions the Adobe PDF Services API as a valuable resource for developers seeking to automate and enhance their document processing capabilities. The availability of the Python SDK is particularly advantageous as it offers a direct and potentially streamlined approach for implementing the desired PDF processing pipeline.

### **1.2 Setting up the Python SDK**

To begin utilizing the Adobe PDF Services API with Python, several preparatory steps are necessary.

#### **1.2.1 Prerequisites**

The Python SDK requires that your system has Python version 3.10 or higher installed 3. This ensures compatibility with the SDK's functionalities and dependencies.

#### **1.2.2 Installation**

The SDK can be easily installed using the Python package installer, pip. Execute the command pip install pdfservices-sdk in your terminal or command prompt to download and install the necessary libraries 3. This command retrieves the pdfservices-sdk package and its dependencies, making them available for use in your Python projects. The simplicity of this installation process aligns with standard Python development practices, making it readily accessible for an AI agent to incorporate into a development workflow.

#### **1.2.3 Obtaining Credentials**

Access to the Adobe PDF Services API necessitates obtaining Adobe-provided credentials 1. This process starts by navigating to the Adobe developer website, where you will be prompted to sign in with an Adobe ID or create a new one if you don't already have one 1. Upon logging in, you will be guided through the creation of a new project, during which you should specify Python as the intended language for integration 1. As part of this credential generation process, a pdfservices-api-credentials.json file containing your unique client ID and client secret will be automatically downloaded to your system 1. These credentials are essential for authenticating your application with the Adobe PDF Services API. The straightforward nature of obtaining these credentials through a web-based workflow simplifies the initial setup phase.

#### **1.2.4 Authentication**

Once the pdfservices-api-credentials.json file is downloaded, the client ID and client secret contained within it need to be configured as environment variables in your development environment 1. This is typically done using the operating system's environment variable settings or directly in your terminal session before running your Python script. For Windows, you would use the set command (e.g., set PDF\_SERVICES\_CLIENT\_ID=\<YOUR CLIENT ID\>), and for macOS or Linux, you would use the export command (e.g., export PDF\_SERVICES\_CLIENT\_ID=\<YOUR CLIENT ID\>) 1. Setting these environment variables allows the Python SDK to securely authenticate with the Adobe PDF Services API without hardcoding sensitive information directly in the code. This method of authentication using environment variables is a common and secure practice in software development.

## **2\. Detailed Examination of Text Extraction**

The Adobe PDF Services API includes the PDF Extract API, a specialized component designed for the purpose of extracting content and structural information from PDF documents 5. This API leverages Adobe's Sensei AI technology to intelligently process both native and scanned PDF files, identifying and extracting various elements such as text, tables, and figures 4. The output of this extraction process is a structured JSON format, which provides a predictable and easily parsable representation of the document's content and organization 4. This structured output is particularly advantageous for automated processing by an AI Coding Agent, as it eliminates the need for complex parsing of unstructured text.

### **2.2 Options for Including or Excluding Footnotes**

A key requirement for the intended PDF processing pipeline is the ability to selectively include or exclude footnotes during text extraction. The PDF Extract API addresses this need by identifying different semantic elements within the document, including footnotes 6. In the structured JSON output, each extracted element is accompanied by a Path attribute that specifies the type of element it represents, such as "Footnote" 6. This detailed structural information allows for precise filtering of the extracted text. By examining the Path attribute of each text block in the JSON output, the pipeline can readily distinguish footnotes from the main body text, enabling the desired selective inclusion or exclusion based on the specific processing requirements. This level of granularity in identifying footnotes as a distinct element type provides the necessary control for customizing the text extraction process.

### **2.3 Structure of the Extracted Text Output**

The PDF Extract API delivers the extracted content as a structured JSON file, which contains an ordered list of semantic elements discovered in the document 4. These elements encompass various components of a PDF, including headings, paragraphs, tables, figures, and footnotes. Each element in the JSON output is described by several attributes that provide contextual information. The Bounds attribute specifies the bounding box coordinates of the element on the page, while the Font attribute details the font properties of the text, and TextSize indicates the size of the text 11. The actual textual content of the element is provided in the Text attribute 11. Crucially for footnote handling, the Path attribute identifies the element's type, allowing for programmatic differentiation of footnotes from other text elements 6. Furthermore, the API can optionally output tables as separate CSV or XLSX files and figures as PNG images, providing flexibility in how different types of content are handled 6. The comprehensive nature of this structured output, with its detailed information about each extracted element, offers a rich dataset for downstream processing and customization.

**Table 1: PDF Extract API Output Structure (Key Attributes)**

| Attribute Name | Description | Relevant for Footnote Handling? |
| :---- | :---- | :---- |
| Elements | Ordered list of semantic elements (headings, paragraphs, tables, figures, footnotes, etc.) | Yes |
| Bounds | Bounding box coordinates of the element | No |
| Font | Font description of the text | No |
| TextSize | Size of the text | No |
| Text | Actual textual content of the element | Yes |
| Path | Location of the element in the document structure tree (includes element type like "Footnote") | Yes |
| Figures | File paths to extracted figures (PNG) | No |
| Tables | File paths to extracted tables (CSV, XLSX, PNG) | No |
| Pages | Properties of each page (number, width, height, rotation) | No |

### **2.4 Code Example for Text Extraction**

The Adobe documentation provides a Python code example that demonstrates how to extract text information from a PDF document using the PDF Services API 4. This example outlines the necessary steps, starting with the creation of credentials using the client ID and client secret obtained earlier. It then proceeds to upload the input PDF file as an asset to the Adobe cloud service. Following the asset upload, parameters for the extraction job are defined. In this specific example, the parameter ExtractElementType.TEXT is used to specify that only text should be extracted. A new extraction job is then created using the uploaded asset and the defined parameters, and this job is submitted to the API. Upon successful submission, the code retrieves the job result, which includes a download URI for the extracted content. Finally, the example demonstrates how to download the result, which is typically a ZIP file containing the structured JSON output with the extracted text. This readily available Python sample provides a practical starting point for the AI Coding Agent to implement the text extraction functionality within the desired pipeline.

Python

`import os`  
`import logging`  
`from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials`  
`from adobe.pdfservices.operation.client_config import ClientConfig`  
`from adobe.pdfservices.operation.pdf_services import PDFServices`  
`from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType`  
`from adobe.pdfservices.operation.extractpdf.extract_pdf_operation import ExtractPDFOperation`  
`from adobe.pdfservices.operation.extractpdf.extract_pdf_options import ExtractPDFOptions`  
`from adobe.pdfservices.operation.extractpdf.extract_element_type import ExtractElementType`  
`from adobe.pdfservices.operation.io.file_ref import FileRef`

`logging.basicConfig(level=logging.INFO)`

`class ExtractTextInfoFromPDF:`  
    `def __init__(self):`  
        `try:`  
            `# Initial setup, create credentials instance.`  
            `credentials = ServicePrincipalCredentials(`  
                `client_id=os.getenv("PDF_SERVICES_CLIENT_ID"),`  
                `client_secret=os.getenv("PDF_SERVICES_CLIENT_SECRET"),`  
            `)`

            `# Creates a PDF Services instance.`  
            `self.pdf_services = PDFServices(credentials=credentials)`  
        `except Exception as e:`  
            `logging.exception(f"Exception encountered during initialization: {e}")`  
            `raise`

    `def extract_text(self, input_pdf_path, output_zip_path):`  
        `try:`  
            `# Create an Asset from the input PDF file.`  
            `input_file = FileRef.create_from_local_file(input_pdf_path)`

            `# Create ExtractPDFOptions`  
            `extract_pdf_options = ExtractPDFOptions.builder() \`  
                `.with_element_to_extract(ExtractElementType.TEXT) \`  
                `.build()`

            `# Create an ExtractPDFOperation instance`  
            `extract_pdf_operation = ExtractPDFOperation.create_new()`

            `# Set the input asset`  
            `extract_pdf_operation.set_input(input_file)`

            `# Set the options for text extraction`  
            `extract_pdf_operation.set_options(extract_pdf_options)`

            `# Execute the operation.`  
            `result: FileRef = self.pdf_services.execute(extract_pdf_operation)`

            `# Save the result to the specified location.`  
            `result.save_as(output_zip_path)`

            `logging.info(f"Successfully extracted text to {output_zip_path}")`

        `except (ServiceApiException, ServiceUsageException, SdkException) as e:`  
            `logging.exception(f"Exception encountered while executing operation: {e}")`

`if __name__ == "__main__":`  
    `# Replace with the actual paths to your input PDF and desired output ZIP file`  
    `input_pdf = "extractPdfInput.pdf"`  
    `output_zip = "extractTextInfoFromPDF.zip"`

    `# Ensure the input file exists`  
    `if not os.path.exists(input_pdf):`  
        `print(f"Error: Input PDF file not found at {input_pdf}")`  
    `else:`  
        `extractor = ExtractTextInfoFromPDF()`  
        `extractor.extract_text(input_pdf, output_zip)`

## **3\. PDF Page Manipulation Capabilities**

The Adobe PDF Services API offers functionalities beyond content extraction, including the ability to manipulate the structure of PDF documents. Two key capabilities in this regard are deleting specific pages and splitting a single PDF into multiple smaller documents 2. These features are essential for the user's requirement of removing non-content pages and potentially chunking large PDFs.

### **3.1 Identifying and Removing Non-Content Pages**

The API provides the functionality to delete pages from a PDF document 2. This capability can be leveraged to remove non-content sections such as copyright pages, publisher information, and indices. However, the API does not inherently identify these types of pages automatically. Implementing the removal of these pages would necessitate an initial step to determine which pages should be removed. This could involve extracting the text content of each page using the PDF Extract API and then analyzing this text for keywords or patterns that are characteristic of these non-content sections. Once the specific page numbers corresponding to these sections are identified, the API's delete page operation can be invoked to modify the PDF accordingly. While the API facilitates page deletion, the intelligence to identify which pages to delete based on their content needs to be implemented through additional logic within the processing pipeline.

### **3.2 Methods for Splitting PDFs into Smaller Documents**

For managing large PDF documents and adhering to potential processing limits, the Adobe PDF Services API offers a dedicated "Split PDF" operation 5. This operation allows a single PDF to be divided into multiple smaller PDF files based on various criteria. The API supports splitting by specifying the maximum number of pages per output file, by defining specific page ranges for each new document, or by indicating the desired number of output files 12. While the provided snippets primarily include code examples for Java and .NET demonstrating how to split a PDF by a fixed number of pages, the underlying principles of authentication, asset upload, job creation with appropriate parameters, job submission, and result download would likely be analogous for the Python SDK. These flexible splitting options are crucial for handling large documents that might exceed the processing capabilities of the text extraction API in a single request.

**Table 2: PDF Splitting Options**

| Splitting Method | Description |
| :---- | :---- |
| By Number of Files | Splits the PDF into a specified number of files, distributing the pages as evenly as possible. |
| By Pages Per File | Splits the PDF into multiple files, with each file containing a maximum specified number of pages. |
| By Page Ranges | Splits the PDF based on explicitly defined page ranges, allowing for precise control over the content of each output file. |

## **4\. Investigating Intelligent PDF Chunking**

The user's requirements include the ability to intelligently carve up a PDF into chunks, ideally based on the table of contents. This would allow for processing the document in logical sections, which is beneficial for downstream applications like semantic search and audiobook creation.

### **4.1 Analyzing the API's Potential for Splitting Based on Structure (Table of Contents)**

Based on the reviewed documentation snippets, there is no explicit functionality within the Adobe PDF Services API to directly split a PDF document based on its table of contents or other inherent structural elements like chapter headings 12. While the PDF Extract API can provide structural information by identifying headings and sections within the document, it does not offer a direct operation to use this information for splitting the PDF into separate files. The available "Split PDF" operation focuses on splitting by page count or predefined page ranges, rather than by semantic structure.

### **4.2 Documenting Limitations and Alternative Approaches**

The absence of a direct "split by structure" feature in the API necessitates exploring alternative approaches to achieve the desired intelligent PDF chunking. One viable method involves a two-step process. First, the PDF Extract API can be used to extract the structured content of the PDF, including the table of contents, which typically lists the page numbers for each section or chapter. The resulting JSON output will contain information about headings and their corresponding page locations. Second, this extracted table of contents data can be programmatically parsed to identify the start and end page numbers for each logical section. Once these page ranges are determined, the API's "Split PDF" functionality, which allows splitting by page ranges, can be used to create separate PDF documents for each section. This approach requires an additional layer of processing to parse the extracted table of contents and then utilize the existing splitting capabilities of the API. It is also important to note that the Adobe text extract API has a page limit per request, although the exact limit is not specified in the provided snippets. This limitation further underscores the need for a chunking strategy, especially for large documents. The table of contents-based approach offers a more semantically meaningful way to chunk the document compared to a simple page-based split.

## **5\. Building a Flexible PDF Processing Pipeline**

To effectively utilize the Adobe PDF Services API for the user's needs, a flexible and modular processing pipeline should be designed. This pipeline should be capable of handling various PDF documents, extracting text with options for including or excluding footnotes, removing non-content pages, and splitting large documents into manageable chunks.

### **5.1 Architectural Considerations**

The architecture of the PDF processing pipeline should prioritize modularity to allow for easy customization of each processing step. This includes options for configuring text extraction parameters, specifying which non-content pages to remove, and choosing the strategy for splitting large PDFs. The pipeline must also handle the authentication process with the Adobe PDF Services API, ensuring that all API requests are properly authorized. Efficient job management, including the creation, submission, polling for status, and downloading of results, is another crucial aspect. The output from the text extraction step, which is a structured JSON file, should be readily accessible for subsequent processing by downstream applications. Finally, robust error handling mechanisms should be implemented to gracefully manage potential issues such as API call failures, large file processing challenges, and adherence to API usage limits.

### **5.2 Potential Integration Points for Downstream Applications**

The primary goal of this pipeline is to produce cleaned and structured text from PDF documents that can be readily used by various downstream applications. One significant application is semantic search. The extracted text can be further processed to generate semantic embeddings using appropriate libraries or services. The structured JSON format of the extracted text can help preserve the context of different text elements during the encoding process, potentially leading to more accurate semantic representations. Another potential use case is the creation of audiobooks using text-to-speech services like Edge TTS. The pipeline's ability to exclude footnotes during text extraction would be particularly relevant in this scenario. The pipeline could process the PDF document in chunks, feeding the extracted text from each chunk to the TTS service to generate corresponding audio segments. The flexibility of the pipeline lies in its ability to produce a standardized output format (cleaned, structured text) that can be easily adapted to the specific requirements of diverse downstream applications.

### **5.3 Handling Large PDFs and API Limits**

Given that the Adobe text extract API has a page limit per request, a strategy for handling large PDFs is essential. The PDF splitting capability of the API should be integrated into the pipeline to divide large documents into smaller, processable chunks. The splitting could be based on a fixed number of pages to ensure that each chunk stays within the API's limits. Ideally, the more intelligent approach of splitting based on the table of contents, as discussed earlier, should be implemented to maintain the logical structure of the document. The pipeline should manage the processing of these chunks sequentially, ensuring that each part of the document is processed and the results are aggregated appropriately for the downstream applications.

## **6\. Conclusion and Recommendations**

The Adobe PDF Services API Python SDK presents a powerful and versatile solution for the user's PDF processing requirements. It offers robust capabilities for text extraction, including the identification of footnotes, and provides functionalities for manipulating PDF documents through page deletion and splitting. The structured JSON output from the PDF Extract API is particularly valuable for creating a flexible processing pipeline that can cater to various downstream applications.

While the API does not offer a direct method for splitting PDFs based on the table of contents, a viable workaround involves using the PDF Extract API to retrieve the table of contents and then utilizing the page range-based splitting functionality. To build a robust and efficient PDF processing pipeline using the Adobe PDF Services API, the following best practices and recommendations should be considered:

* Implement comprehensive error handling and logging to ensure the pipeline is resilient to potential issues.  
* Securely manage the API credentials to prevent unauthorized access.  
* Determine the exact page limits for the text extraction API to implement an effective splitting strategy for large documents.  
* Develop a module to parse the table of contents from the extracted JSON output and use this information to split the PDF into logical chunks based on sections or chapters.  
* Provide configuration options within the pipeline to allow users to specify whether footnotes should be included in the extracted text and whether non-content pages should be removed.  
* Leverage the provided sample code in the Adobe documentation as a starting point for implementing the various functionalities within the pipeline, adapting it to the specific requirements.

By following these recommendations, a highly customizable and effective PDF processing pipeline can be developed using the Adobe PDF Services API Python SDK, meeting the user's needs for creating cleaned text files suitable for semantic encoding and audiobook generation.

#### **Works cited**

1\. Getting Started | PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/gettingstarted/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/gettingstarted/)  
2\. PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/)  
3\. Adobe PDFServices Python SDK \- GitHub, accessed March 15, 2025, [https://github.com/adobe/pdfservices-python-sdk](https://github.com/adobe/pdfservices-python-sdk)  
4\. PDF Tools APIs | Adobe Acrobat Services, accessed March 15, 2025, [https://www.adobe.io/document-services/apis/pdf-services/](https://www.adobe.io/document-services/apis/pdf-services/)  
5\. SDK Developer Kit | PDF Library | Adobe Acrobat Services, accessed March 15, 2025, [https://developer.adobe.com/document-services/](https://developer.adobe.com/document-services/)  
6\. Adobe PDF Extract API Technical Brief, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/assets/268b4618cd5696a95ebf8cc01de5f310/Adobe\_PDF\_Extract\_API\_Technical\_Brief.pdf](https://developer.adobe.com/document-services/docs/assets/268b4618cd5696a95ebf8cc01de5f310/Adobe_PDF_Extract_API_Technical_Brief.pdf)  
7\. Python | Quickstarts | Document Generation API | Adobe PDF Services, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/document-generation-api/quickstarts/python/](https://developer.adobe.com/document-services/docs/overview/document-generation-api/quickstarts/python/)  
8\. Quickstart for Adobe PDF Services API (Python), accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/quickstarts/python/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/quickstarts/python/)  
9\. PDF Extract API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/](https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/)  
10\. Extract Text from PDF | Extract Data from PDF | Visualizer \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/apis/pdf-extract/](https://developer.adobe.com/document-services/apis/pdf-extract/)  
11\. How Tos | PDF Extract API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-extract-api/howtos/extract-api/](https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-extract-api/howtos/extract-api/)  
12\. Split PDF | How Tos | PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/split-pdf/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/split-pdf/)  
13\. Split PDF | How Tos | PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-services-api/howtos/split-pdf/](https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-services-api/howtos/split-pdf/)  
14\. PDF Services API — Split PDF Pages \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/apis/pdf-services/split-pdf/](https://developer.adobe.com/document-services/apis/pdf-services/split-pdf/)