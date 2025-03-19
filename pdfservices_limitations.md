# **Limitations of the Adobe PDF Extract API: Page Limits, Document Size, and Parallel Processing**

**1\. Introduction**

The Adobe PDF Extract API, a component of the broader Adobe PDF Services API, offers a cloud-based solution for automatically extracting content and structural information from PDF documents, whether native or scanned. This service utilizes Adobe Sensei AI technology to identify and output text, tables, and figures in a structured JSON format 1. Understanding the operational boundaries of this API is crucial for developers and organizations aiming to integrate it into their workflows. Recognizing these limitations ensures efficient resource allocation, prevents unexpected errors during processing, and allows for the implementation of appropriate strategies when dealing with documents that approach or exceed these boundaries. This report specifically examines the limitations of the Adobe PDF Extract API concerning page limits, maximum document size, and parallel processing capabilities.

**2\. Page Limit Restrictions**

The Adobe PDF Extract API imposes restrictions on the number of pages it can process within a single request, and these limits vary based on whether the PDF document is a native digital file or a scanned image.

**2.1. Non-Scanned PDF Page Limit:**

For non-scanned PDF documents, the primary limitation is set at **400 pages** 4. This indicates that for digitally created PDFs with selectable text, the API can handle documents of significant length. However, it's important to note that some documentation suggests a lower limit of **200 pages** for non-scanned PDFs 10. This discrepancy could stem from variations in API versions, specific service tiers, or perhaps represent an earlier limitation that has since been updated. The more frequently cited and current documentation points towards the 400-page limit.

Furthermore, the stated page limit for non-scanned PDFs is not absolute and can be reduced for files containing a large number of tables or those with complex layouts 4. This suggests that the API's processing capacity is influenced not just by the sheer number of pages but also by the complexity and density of the content on those pages. Extracting structured information from numerous or intricate tables likely demands more computational resources. Consequently, users might encounter processing failures even with documents under the nominal page limit if they contain exceptionally complex elements. When the page limit for a non-scanned document is exceeded, the API returns the error code DISQUALIFIED\_PAGE\_LIMIT 7.

**2.2. Scanned PDF Page Limit:**

The limitation for scanned PDF documents is considerably lower, set at **150 pages or less** 4. This reduction reflects the additional processing overhead required for scanned documents, which typically involves Optical Character Recognition (OCR) to convert images of text into machine-readable text. This process is computationally intensive and thus necessitates a stricter page limit to ensure efficient operation. Similar to non-scanned PDFs, this limit can also be lower for scanned files that contain multiple tables 4. If a scanned document surpasses this page threshold, the API will respond with the error code DISQUALIFIED\_SCAN\_PAGE\_LIMIT 7. The significant difference in page limits between scanned and non-scanned documents underscores the performance trade-offs inherent in processing different types of PDF files.

**2.3. Page Limits and Document Transactions:**

Beyond the absolute page limits, the Adobe PDF Extract API's licensing model, based on Document Transactions, also introduces a page-related constraint. For the specific operation of extracting content from a PDF, each Document Transaction covers **up to 5 pages** 9. This means that even if a document falls within the 400-page (non-scanned) or 150-page (scanned) limit, processing it might consume multiple Document Transactions. For instance, extracting content from an 8-page PDF document will require two Document Transactions 9. This transactional model implies a direct relationship between the number of pages processed and the cost of using the API, particularly relevant for high-volume processing scenarios. In contrast, other operations within the Adobe PDF Services API, such as combining or compressing PDFs, typically allow for up to 50 pages per Document Transaction 9. The significantly lower page count per transaction for the Extract API suggests that Adobe considers content extraction a more resource-intensive operation compared to other PDF manipulation tasks.

**3\. Maximum Document Size Constraints**

In addition to page count, the Adobe PDF Extract API also imposes a limit on the maximum file size of the PDF document submitted for processing. This limit is set at **100MB** 5. This constraint applies regardless of the number of pages within the document, as long as it also adheres to the page limits. The file size restriction likely exists to manage the total volume of data that the API needs to handle for a single request, potentially related to memory limitations during processing or network transfer efficiency. When a submitted PDF file exceeds this 100MB limit, the API will return error messages such as DISQUALIFIED\_FILE\_SIZE or BAD\_PDF\_LARGE\_FILE 7. This size limitation necessitates that users ensure their PDF documents are within this threshold before attempting to extract content.

**4\. Parallel Processing Capabilities and Rate Limits**

Understanding the parallel processing capabilities of the Adobe PDF Extract API is important for optimizing workflows, especially when dealing with a large number of documents. However, the available documentation does not explicitly detail user-configurable options for parallel processing within a single API request for a given document.

**4.1. Parallel Processing:**

While one snippet mentions "Parallel processing" 15, it does so in the context of the "Streaming summaries for long PDFs" feature within Acrobat or Acrobat Reader, rather than as a direct capability exposed for developers using the Extract API. This suggests that while Adobe's end-user products might leverage parallel processing internally for certain functionalities, it is not presented as a feature that developers can directly control or configure when using the PDF Extract API. The focus of the developer documentation leans more towards managing the overall volume of requests through rate limits, implying that handling high-throughput scenarios primarily involves controlling the number of API calls rather than adjusting the parallelism of processing within each call. The absence of explicit documentation on parallel processing for the Extract API indicates that the API likely manages its internal processing mechanisms without offering developers direct control over concurrency for a single document.

**4.2. Rate Limits:**

The Adobe PDF Services API, which includes the Extract API, enforces rate limits to ensure fair usage and maintain service stability. The standard rate limit is **25 requests per minute (RPM)** 5. This means that an application utilizing the Extract API should not exceed 25 API calls within any 60-second window. For users with Enterprise-level subscriptions, a higher rate limit of **100 RPM** might be available 9. These rate limits have direct implications for processing multiple documents or large volumes of data. For example, adhering to the standard 25 RPM limit would mean that processing 100 individual documents would take a minimum of 4 minutes. Similarly, even with the Enterprise tier's 100 RPM limit, the same task would require at least 1 minute. These limitations necessitate that developers integrating the Adobe PDF Extract API into their applications design their systems to respect these rate limits, potentially by implementing queuing mechanisms or throttling logic to avoid exceeding the allowed number of requests per minute. This careful management of request volume is crucial for preventing service disruptions and ensuring consistent performance.

**5\. Strategies for Handling Documents Exceeding Limitations**

When faced with PDF documents that exceed the page limits or the maximum file size of the Adobe PDF Extract API, the primary recommended strategy is to divide the larger files into smaller, more manageable sections before attempting to process them 4.

**5.1. Splitting Large Documents:**

Adobe explicitly advises splitting larger files as a prerequisite for processing with the Extract API 4. The Adobe PDF Services API offers a dedicated **Split PDF operation** that can be used programmatically to achieve this division 10. This operation allows for splitting a PDF document into multiple smaller documents based on either a specified number of pages per file or by defining specific page ranges 17. This flexibility in splitting methods enables developers to tailor the process to their specific needs. For instance, they might choose to split a large report into sections of a fixed number of pages or to divide a document based on its logical chapters or parts by specifying page ranges.

**5.2. Considerations for Splitting:**

While splitting a large PDF into smaller chunks addresses the API's limitations on size and page count, it also introduces certain considerations. One user raised a concern about the potential loss of context when splitting documents, particularly concerning elements like the "Path" information provided by the Extract API, which describes the location of elements within the document structure 10. When a document is split, the extracted data from each resulting part might need to be reassembled or correlated if maintaining the original document's overall context is crucial for the application's logic. Therefore, developers might need to implement additional logic to handle the fragmented data and reconstruct the necessary context after processing the split sections. This could involve tracking the order of the split documents or using metadata to link the extracted information back to its original location within the larger document.

**6\. Licensing and Usage Considerations**

As previously mentioned, the Adobe PDF Extract API utilizes a Document Transaction-based licensing model. Specifically, the "Extract PDF" operation consumes one Document Transaction for every five pages of the processed document 9. For example, a 12-page document would require three Document Transactions (as 12 divided by 5 rounds up to 3). Understanding this cost structure is essential for managing the expenses associated with using the API, especially in scenarios involving a high volume of multi-page documents. Adobe offers a Free Tier for the PDF Services API, which includes 500 free Document Transactions per month 2. This allows developers to explore the API's capabilities and integrate it into their applications with a limited initial quota. However, for production environments or applications that process a significant number of documents, careful consideration of the transactional costs is necessary. The low page count per transaction for the Extract API, compared to other PDF Services operations, highlights the potentially higher cost associated with extracting detailed content from PDF documents.

**7\. Error Scenarios and Messages**

The Adobe PDF Extract API provides specific error codes to indicate when a processing request fails due to exceeding its limitations 5. These error codes are valuable for developers as they provide clear reasons for the failure, enabling them to implement appropriate error handling and potentially retry mechanisms, often involving splitting the document. The relevant error codes include:

* DISQUALIFIED\_FILE\_SIZE: This error indicates that the submitted PDF file exceeds the maximum allowed size of 100MB.  
* DISQUALIFIED\_PAGE\_LIMIT: This error is returned when a non-scanned PDF document exceeds the page limit (typically 400 pages).  
* DISQUALIFIED\_SCAN\_PAGE\_LIMIT: This error signifies that a scanned PDF document has exceeded its page limit (typically 150 pages).  
* BAD\_PDF\_LARGE\_FILE: This error also indicates that the input file size is too large.  
* TIMEOUT: While not exclusively related to size or page limits, a TIMEOUT error can occur when processing very large or complex files that exceed the API's processing time constraints. The error message often suggests splitting the file into smaller parts.

These explicit error messages allow developers to diagnose the cause of processing failures and take corrective actions, such as splitting the document or checking the file size before submitting it to the API.

**8\. Conclusion**

The Adobe PDF Extract API offers a powerful solution for extracting structured data from PDF documents, but it operates within specific limitations concerning page count, document size, and processing rates. Non-scanned PDFs are generally limited to 400 pages (though some older documentation suggests 200), while scanned PDFs have a stricter limit of 150 pages. These limits can be further reduced for documents with numerous or complex tables. The maximum supported file size for any PDF is 100MB. Regarding processing volume, the API is subject to a rate limit of 25 requests per minute for standard users (and potentially 100 RPM for enterprise users). Furthermore, the Extract PDF operation is licensed based on Document Transactions, with one transaction covering up to five pages.

The primary strategy recommended by Adobe for handling documents that exceed these limitations is to split them into smaller, more manageable sections using the Split PDF operation available within the PDF Services API. While this approach allows for the processing of larger documents, developers need to consider the potential implications of splitting, such as the need to reassemble context from the extracted data. Understanding these limitations and the available strategies is crucial for effectively integrating the Adobe PDF Extract API into applications and ensuring efficient and cost-effective document processing workflows.

**Table 1: Adobe PDF Extract API Limitations**

| Limitation Category | Constraint | Snippet References | Report Section |
| :---- | :---- | :---- | :---- |
| **Page Limits** | Non-Scanned PDFs: 400 pages (potentially lower) | 4 | 2.1 |
|  | Non-Scanned PDFs: 200 pages (potential older limit) | 10 | 2.1 |
|  | Scanned PDFs: 150 pages or less (potentially lower) | 4 | 2.2 |
| **Maximum Document Size** | 100MB | 5 | 3 |
| **Rate Limits** | 25 requests per minute (RPM) | 5 | 4.2 |
|  | 100 requests per minute (RPM) (Enterprise) | 9 | 4.2 |
| **Document Transactions** | Extract PDF: up to 5 pages per Document Transaction | 9 | 2.3, 6 |

**Table 2: Adobe PDF Extract API Error Codes Related to Limitations**

| Error Code | Description | Snippet References | Report Section |
| :---- | :---- | :---- | :---- |
| DISQUALIFIED\_FILE\_SIZE | File exceeds size limit. | 7 | 3, 7 |
| DISQUALIFIED\_PAGE\_LIMIT | File exceeds page limit for non-scanned documents. | 7 | 2.1, 7 |
| DISQUALIFIED\_SCAN\_PAGE\_LIMIT | Scanned file exceeds page limit. | 7 | 2.2, 7 |
| BAD\_PDF\_LARGE\_FILE | The input file size exceeds the maximum allowed. | 7 | 3, 7 |
| TIMEOUT | Processing timeout (often due to large files). | 7 | 7 |

#### **Works cited**

1\. PDF Extract API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/](https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/)  
2\. Extract Text from PDF | Extract Data from PDF | Visualizer \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/apis/pdf-extract/](https://developer.adobe.com/document-services/apis/pdf-extract/)  
3\. Adobe PDF Services, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/](https://developer.adobe.com/document-services/docs/overview/)  
4\. developer.adobe.com, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/howtos/extract-api/\#:\~:text=API%20limitations\&text=Number%20of%20Pages%3A%20Non%2Dscanned,into%20smaller%20sections%20before%20processing.](https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/howtos/extract-api/#:~:text=API%20limitations&text=Number%20of%20Pages%3A%20Non%2Dscanned,into%20smaller%20sections%20before%20processing.)  
5\. How Tos | PDF Extract API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/howtos/extract-api/](https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/howtos/extract-api/)  
6\. developer.adobe.com, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/extract-pdf/\#:\~:text=API%20limitations,of%20150%20pages%20or%20less.](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/extract-pdf/#:~:text=API%20limitations,of%20150%20pages%20or%20less.)  
7\. How Tos | PDF Extract API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/extract-pdf/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/extract-pdf/)  
8\. From Unstructured to Structured: Adobe PDF Extract API for Data Transformation, accessed March 15, 2025, [https://dev.to/theblogsquad/from-unstructured-to-structured-adobe-pdf-extract-api-for-data-transformation-1n08](https://dev.to/theblogsquad/from-unstructured-to-structured-adobe-pdf-extract-api-for-data-transformation-1n08)  
9\. Licensing and Usage Limits \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/limits/](https://developer.adobe.com/document-services/docs/overview/limits/)  
10\. Re: Processing larger documents on extract API? \- Adobe ..., accessed March 15, 2025, [https://community.adobe.com/t5/document-services-apis-discussions/processing-larger-documents-on-extract-api/m-p/13142490](https://community.adobe.com/t5/document-services-apis-discussions/processing-larger-documents-on-extract-api/m-p/13142490)  
11\. What is the optimal PDF page length to hit the PDF Extract API? \- Adobe Community, accessed March 15, 2025, [https://community.adobe.com/t5/acrobat-services-api-discussions/what-is-the-optimal-pdf-page-length-to-hit-the-pdf-extract-api/td-p/12439792](https://community.adobe.com/t5/acrobat-services-api-discussions/what-is-the-optimal-pdf-page-length-to-hit-the-pdf-extract-api/td-p/12439792)  
12\. Adobe Doc Generation API- Usage Limits, accessed March 15, 2025, [https://community.adobe.com/t5/acrobat-services-api-discussions/adobe-doc-generation-api-usage-limits/td-p/13164550](https://community.adobe.com/t5/acrobat-services-api-discussions/adobe-doc-generation-api-usage-limits/td-p/13164550)  
13\. PDF Accessibility Auto-Tag API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-accessibility-auto-tag-api/howtos/accessibility-auto-tag-api/](https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-accessibility-auto-tag-api/howtos/accessibility-auto-tag-api/)  
14\. PDF Services API Licensing \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/dcserviceslicensing/](https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/dcserviceslicensing/)  
15\. Get AI-generated overview and summaries \- Adobe Support, accessed March 15, 2025, [https://helpx.adobe.com/acrobat/using/ai-generated-summaries.html](https://helpx.adobe.com/acrobat/using/ai-generated-summaries.html)  
16\. Split PDFs \- Adobe Support, accessed March 15, 2025, [https://helpx.adobe.com/acrobat/web/edit-pdfs/organize-documents/split-pdfs.html](https://helpx.adobe.com/acrobat/web/edit-pdfs/organize-documents/split-pdfs.html)  
17\. PDF Services API — Split PDF Pages \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/apis/pdf-services/split-pdf/](https://developer.adobe.com/document-services/apis/pdf-services/split-pdf/)  
18\. Split PDF | How Tos | PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/split-pdf/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/split-pdf/)  
19\. Split PDF | How Tos | PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-services-api/howtos/split-pdf/](https://developer.adobe.com/document-services/docs/overview/legacy-documentation/pdf-services-api/howtos/split-pdf/)  
20\. PDF Tools APIs | Adobe Acrobat Services, accessed March 15, 2025, [https://www.adobe.io/document-services/apis/pdf-services/](https://www.adobe.io/document-services/apis/pdf-services/)  
21\. Quickstart for Adobe PDF Services API (Python), accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/quickstarts/python/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/quickstarts/python/)  
22\. How Tos | PDF Services API \- Adobe Developer, accessed March 15, 2025, [https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/)