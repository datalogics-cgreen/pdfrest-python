# pdfrest documentation

Welcome to the docs for `pdfrest`, a Python client for
[pdfRest](https://pdfrest.com/).

## What is pdfRest?

[pdfRest](https://pdfrest.com/) is a cloud PDF processing platform that
provides REST APIs for common document workflows such as conversion,
compression, OCR, merge/split, and redaction. You send API requests to the
pdfRest service, and pdfRest returns structured responses and processed file
outputs.

Useful references:

- [pdfRest homepage](https://pdfrest.com/)
- [API reference](https://pdfrest.com/apidocs/)
- [API Lab (interactive testing)](https://pdfrest.com/apilab/)
- [Getting started guide](getting-started.md)
- [Client configuration guide](client-configuration.md)
- [Using files guide](using-files.md)

## How this Python API relates to pdfRest

This repository provides the official Python SDK layer for calling pdfRest
endpoints from Python applications.

The SDK:

- Targets the pdfRest API host (`https://api.pdfrest.com`) by default.
- Exposes both sync and async clients (`PdfRestClient` and
  `AsyncPdfRestClient`).
- Provides typed request/response models and validation to make integrations
  safer and easier to maintain.
- Includes endpoint helpers that map Python method calls to pdfRest API routes.

In short: pdfRest is the hosted API service, and this package is the Python
developer interface for using that service in your code.

## Ways to run pdfRest

The pdfRest docs describe three deployment options:

- [Cloud](https://docs.pdfrest.com/pdfrest-api-toolkit-cloud/getting-started/):
  fastest path with pdfRest-managed infrastructure at `api.pdfrest.com`.
- [On AWS](https://docs.pdfrest.com/pdfrest-api-toolkit-on-aws/getting-started/):
  self-hosted deployment in your AWS environment (AMI or CloudFormation).
- [Container](https://docs.pdfrest.com/pdfrest-api-toolkit-container/getting-started/):
  self-hosted Docker/Kubernetes deployment for private cloud or on-prem.

For this SDK, the integration surface stays consistent across all three:

- Use the default client settings for Cloud.
- Point the client `base_url` at your deployed endpoint for AWS or Container.
- Keep using the same Python methods and payload models; only deployment
  configuration changes.

Reference:

- [pdfRest documentation overview](https://docs.pdfrest.com/overview/)
- [API reference guide directory](https://docs.pdfrest.com/api-reference-guides/directory/)
