import os
import shutil
import json
import base64
import requests
import pandas as pd
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage
from django.apps import apps
from django.db import models, connection, IntegrityError
from .models import Invoice, LineItem, ExcelData, uploadedInvoice, Project
from .forms import ProjectForm


def first_page(request):
    return render(request, 'first.html')

def home(request):
    # Get all data from the Invoice and ExcelData models
    invoices_from_db = Invoice.objects.all()
    actual_from_db = ExcelData.objects.all()
    print("actual", actual_from_db)

    # Combine data for comparison
    combined_data = []
    for invoice_data in invoices_from_db:
        for actual_data in actual_from_db:
            if invoice_data.invoice_number == actual_data.invoice_number:
                combined_data.append({
                    'invoice': invoice_data,
                    'exceldata': actual_data,
                    'image_path': invoice_data.image_path  # Add image_path here
                })
                break

    # Calculate the percentage of correct cells and update the expected_result field
    for data in combined_data:
        total_cells = 0
        correct_cells = 0

        # Iterate over the fields in Invoice and ExcelData models
        for field in Invoice._meta.fields:
            # Exclude non-comparable fields like id, test_id, lineitem, and image_path
            if field.name not in ['id', 'test_id', 'lineitem', 'image_path']:
                total_cells += 1

                # Get the values from Invoice and ExcelData (case-insensitive)
                invoice_value = getattr(data['invoice'], field.name)
                excel_value = getattr(data['exceldata'], field.name)

                # Check if values are not None before converting to lowercase
                if invoice_value is not None and excel_value is not None:
                    invoice_value_lower = invoice_value.lower()
                    excel_value_lower = excel_value.lower()

                    # Compare values (case-insensitive)
                    if invoice_value_lower == excel_value_lower:
                        correct_cells += 1

        # Calculate the percentage of correct cells
        percentage_correct = (correct_cells / total_cells) * 100 if total_cells > 0 else 0

        # Update the expected_result field in ExcelData model
        data['exceldata'].expected_result = percentage_correct
        data['exceldata'].save()

    return render(request, 'home.html', {'combined_data': combined_data})

def send_excel_data_to_database(file_path):
    # Read the Excel file
    excel_data = pd.read_excel(file_path)

    # Loop through each row in the Excel file
    for index, row in excel_data.iterrows():
        # Check if the data already exists in the ExcelData table
        if not ExcelData.objects.filter(invoice_number=row['INVOICE_NUMBER']).exists():
            # Create ExcelData instance and save it to the database
            excel_instance = ExcelData(
                image_name=row['IMAGE_NAME'],
                invoice_number=row['INVOICE_NUMBER'],
                buyer_name=row['BUYER_NAME'],
                buyer_address=row['BUYER_ADDRESS'],
                due_date=row['DUE_DATE'],
                invoice_date=row['INVOICE_DATE'],
                total=row['TOTAL'],
                seller_name=row['SELLER_NAME'],
                seller_address=row['SELLER_ADDRESS'],
                tax=row['TAX'],
                discount=row['DISCOUNT'],
                payment_details=row['PAYMENT_DETAILS'],
                currency=row['CURRENCY'],
                item_description=row['ITEM_DESCRIPTION']
            )
            excel_instance.save()

def start_test(request):
    # Update the file path to the location of the Excel file
    excel_file_path = "/home/machine_6/chaitanya/project3/invoice/static/Invoice/ground_truth.xlsx"
    
    # Call the function to upload Excel data to the database
    send_excel_data_to_database(excel_file_path)

    api_endpoint = "https://sayana-invoice-api-v3ftowcoqq-uc.a.run.app/api/invoice/v1/invoice_detection"
    image_directory = "/home/machine_6/chaitanya/project3/invoice/bills/static/testing_90_images"
    relative_path = "../static/testing_90_images"

    test_id = Invoice.generate_test_id()  # Assuming this function generates a unique test ID
    invoice_instance = Invoice(test_id=test_id)
    invoice_instance.save()

    response_data = {'status': 'Images sent successfully', 'image_responses': []}

    for filename in os.listdir(image_directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(image_directory, filename)
            image_name = filename
            with open(image_path, "rb") as file:
                # Read binary data from the image file
                image_data = file.read()

                # Encode binary data as base64 and decode to a string
                base64_image = base64.b64encode(image_data).decode('ascii')

                # Construct request body
                body = {
                    "image_id": "123",
                    "image_content": base64_image
                }

                try:
                    # Send the POST request to the API endpoint with JSON data
                    response = requests.post(api_endpoint, json=body)
                    if response.status_code == 200:
                        # Parse the response JSON
                        response_data_image = response.json()

                        # Extract relevant data
                        invoice_data = response_data_image.get('Recognition', {})
                        table_data = invoice_data.get('table', [])

                        # Create Invoice instance
                        invoice = Invoice(
                            test_id=test_id,
                            image_name=image_name,  # Add this line
                            image_path=relative_path,  # now we are storing imagepath aswll
                            invoice_number=invoice_data.get('INVOICE_NUMBER', ''),
                            buyer_name=invoice_data.get('BUYER_NAME', ''),
                            buyer_address=invoice_data.get('BUYER_ADDRESS', ''),
                            due_date=None if invoice_data.get('DUE_DATE', '-') == '-' else invoice_data.get(
                                'DUE_DATE', ''),
                            invoice_date=None if invoice_data.get('INVOICE_DATE', '-') == '-' else invoice_data.get(
                                'INVOICE_DATE', ''),
                            total=invoice_data.get('TOTAL', ''),
                            seller_name=invoice_data.get('SELLER_NAME', ''),
                            seller_address=invoice_data.get('SELLER_ADDRESS', ''),
                            tax=invoice_data.get('TAX', ''),
                            discount=invoice_data.get('DISCOUNT', ''),
                            payment_details=invoice_data.get('PAYMENT_DETAILS', ''),
                            currency=invoice_data.get('CURRENCY', '')

                        )
                        invoice.save()

                        # Create LineItem instances
                        for item in table_data:
                            line_item = LineItem(
                                invoice_number=invoice,
                                item_description=item.get('ITEM_DESCRIPTION', ''),
                                unit_price=item.get('UNIT_PRICE', ''),
                                quantity=item.get('QUANTITY', ''),
                                amount=item.get('AMOUNT', ''),
                            )
                            line_item.save()

                        print(f"Image {filename} processed successfully.")
                        print("Response:", json.dumps(response_data_image, indent=4))
                        response_data['image_responses'].append(response_data_image)
                    else:
                        print(f"Error processing image {filename}: {response.status_code} {response.text}")
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while processing image {filename}: {e}")

    return JsonResponse(response_data)

def select_test(request):
    # Get all available test IDs
    test_ids = set(Invoice.objects.values_list('test_id', flat=True))

    if request.method == 'POST':
        selected_test_id = request.POST.get('selected_test_id')
        # Filter invoices and actual data based on the selected test ID
        invoices_from_db = Invoice.objects.filter(test_id=selected_test_id)
        actual_from_db = ExcelData.objects.all()
        combined_data = []
        for invoice_data in invoices_from_db:
            for actual_data in actual_from_db:
                if invoice_data.invoice_number == actual_data.invoice_number:
                    # Calculate the percentage of correct cells for the current data
                    total_cells = 0
                    correct_cells = 0
                    for field in Invoice._meta.fields:
                        # Exclude non-comparable fields like id, test_id, lineitem, and image_path
                        if field.name not in ['id', 'test_id', 'lineitem', 'image_path']:
                            total_cells += 1

                            # Get the values from Invoice and ExcelData (case-insensitive)
                            invoice_value = getattr(invoice_data, field.name)
                            excel_value = getattr(actual_data, field.name)

                            # Check if values are not None before converting to lowercase
                            if invoice_value is not None and excel_value is not None:
                                invoice_value_lower = invoice_value.lower()
                                excel_value_lower = excel_value.lower()

                                # Compare values (case-insensitive)
                                if invoice_value_lower == excel_value_lower:
                                    correct_cells += 1

                    # Calculate the percentage of correct cells
                    percentage_correct = (correct_cells / total_cells) * 100 if total_cells > 0 else 0

                    combined_data.append({
                        'invoice': invoice_data,
                        'exceldata': actual_data,
                        'image_path': invoice_data.image_path,
                        'percentage_correct': percentage_correct  # Add percentage_correct here
                    })
                    break

        return render(request, 'view_results.html', {'combined_data': combined_data})
    else:
        return render(request, 'select_test.html', {'test_ids': test_ids})

def view_results(request):
    # Get all data from the Invoice and ExcelData models
    invoices_from_db = Invoice.objects.all()
    actual_from_db = ExcelData.objects.all()

    # Combine data for comparison
    combined_data = []
    for invoice_data in invoices_from_db:
        for actual_data in actual_from_db:
            if invoice_data.invoice_number == actual_data.invoice_number:
                total_cells = 0
                correct_cells = 0

                # Iterate over the fields in Invoice and ExcelData models
                for field in Invoice._meta.fields:
                    # Exclude non-comparable fields like id, test_id, lineitem, and image_path
                    if field.name not in ['id', 'test_id', 'lineitem', 'image_path']:
                        total_cells += 1

                        # Get the values from Invoice and ExcelData (case-insensitive)
                        invoice_value = getattr(invoice_data, field.name)
                        excel_value = getattr(actual_data, field.name)

                        # Check if values are not None before converting to lowercase
                        if invoice_value is not None and excel_value is not None:
                            invoice_value_lower = invoice_value.lower()
                            excel_value_lower = excel_value.lower()

                            # Compare values (case-insensitive)
                            if invoice_value_lower == excel_value_lower:
                                correct_cells += 1

                # Calculate the percentage of correct cells
                percentage_correct = (correct_cells / total_cells) * 100 if total_cells > 0 else 0

                # Update the expected_result field in ExcelData model
                actual_data.expected_result = percentage_correct
                actual_data.save()

                # Append the data to combined_data including percentage_correct
                combined_data.append({
                    'invoice': invoice_data,
                    'exceldata': actual_data,
                    'image_path': invoice_data.image_path,
                    'percentage_correct': percentage_correct  # Add percentage_correct here
                })

    return render(request, 'view_results.html', {'combined_data': combined_data})

def upload_invoice(request):
    if request.method == 'POST' and request.FILES.get('invoice_file'):
        invoice_file = request.FILES['invoice_file']
        base64_image = base64.b64encode(invoice_file.read()).decode('ascii')

        # Send the file to the external API
        api_url = "https://sayana-invoice-api-v3ftowcoqq-uc.a.run.app/api/invoice/v1/invoice_detection"
        body = {
            "image_id": "123",
            "image_content": base64_image
        }
        response = requests.post(api_url, json=body)

        if response.status_code == 200:
            # Parse the response JSON
            response_data = response.json()

            # Extract relevant data
            invoice_data = response_data.get('Recognition', {})
            table_data = invoice_data.get('table', [])

            # Save response data to the model
            invoice_instance = uploadedInvoice(
                invoice_number=invoice_data.get('INVOICE_NUMBER', ''),
                buyer_name=invoice_data.get('BUYER_NAME', ''),
                buyer_address=invoice_data.get('BUYER_ADDRESS', ''),
                due_date=invoice_data.get('DUE_DATE', ''),
                invoice_date=invoice_data.get('INVOICE_DATE', ''),
                total=invoice_data.get('TOTAL', ''),
                seller_name=invoice_data.get('SELLER_NAME', ''),
                seller_address=invoice_data.get('SELLER_ADDRESS', ''),
                tax=invoice_data.get('TAX', ''),
                discount=invoice_data.get('DISCOUNT', ''),
                payment_details=invoice_data.get('PAYMENT_DETAILS', ''),
                currency=invoice_data.get('currency', '')  # Use 'currency' instead of 'CURRENCY'
            )
            invoice_instance.save()

            # Pretty print the JSON response for better readability
            pretty_response = json.dumps(response_data, indent=4)

            # Retrieve only the last uploaded invoice
            last_uploaded_invoice = uploadedInvoice.objects.last()  

            # Render the response data of the last uploaded invoice in a table format on the frontend
            return render(request, 'invoice_details.html', {'pretty_response': pretty_response, 'invoice_data': last_uploaded_invoice})

        else:
            return JsonResponse({'error': 'Failed to process the invoice'}, status=500)

    else:
        # If GET request, just render the upload form
        return render(request, 'upload.html')
    
def upload_invoice_folder(request):
    if request.method == 'POST' and request.FILES.getlist('invoice_files'):
        invoice_files = request.FILES.getlist('invoice_files')
        new_invoices = []

        for invoice_file in invoice_files:
            base64_image = base64.b64encode(invoice_file.read()).decode('ascii')
            api_url = "https://sayana-invoice-api-v3ftowcoqq-uc.a.run.app/api/invoice/v1/invoice_detection"
            body = {
                "image_id": "123",
                "image_content": base64_image
            }
            response = requests.post(api_url, json=body)

            if response.status_code == 200:
                response_data = response.json()
                invoice_data = response_data.get('Recognition', {})
                invoice_instance = uploadedInvoice(
                    invoice_number=invoice_data.get('INVOICE_NUMBER', ''),
                    buyer_name=invoice_data.get('BUYER_NAME', ''),
                    buyer_address=invoice_data.get('BUYER_ADDRESS', ''),
                    due_date=invoice_data.get('DUE_DATE', ''),
                    invoice_date=invoice_data.get('INVOICE_DATE', ''),
                    total=invoice_data.get('TOTAL', ''),
                    seller_name=invoice_data.get('SELLER_NAME', ''),
                    seller_address=invoice_data.get('SELLER_ADDRESS', ''),
                    tax=invoice_data.get('TAX', ''),
                    discount=invoice_data.get('DISCOUNT', ''),
                    payment_details=invoice_data.get('PAYMENT_DETAILS', ''),
                    currency=invoice_data.get('currency', '')
                )
                invoice_instance.save()
                new_invoices.append(invoice_instance)

        # Store the new invoice IDs in the session
        request.session['new_invoice_ids'] = [invoice.id for invoice in new_invoices]

        return render(request, 'invoice_details.html', {'invoices': new_invoices})

    else:
        return render(request, 'upload_folder.html')

    
def download_excel(request):
    # Get the new invoice IDs from the session
    new_invoice_ids = request.session.get('new_invoice_ids', [])
    
    # Retrieve only the new invoices from the database
    new_invoices = uploadedInvoice.objects.filter(id__in=new_invoice_ids).values()
    
    # Convert the query set to a DataFrame
    df = pd.DataFrame(new_invoices)
    
    # Create a HTTP response with the Excel file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=invoices.xlsx'
    df.to_excel(response, index=False)
    
    return response




def invoice_details_view(request):
    # Retrieve the last uploaded invoice from the database
    last_uploaded_invoice = uploadedInvoice.objects.last()

    # Pass the retrieved invoice to the template
    return render(request, 'invoice_details.html', {'invoice_data': last_uploaded_invoice})




####Dyanamic part starts
import logging

logger = logging.getLogger(__name__)


def choose_test(request):
    projects = Project.objects.all()
    has_projects = projects.exists()
    return render(request, 'choose_test.html', {'projects': projects, 'has_projects': has_projects})


def register_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            ground_truth = request.FILES['ground_truth']
            test_data_directory = request.FILES['test_data_directory']

            project.ground_truth_file = ground_truth.name
            project.test_data_directory = test_data_directory.name

            project_dir = os.path.join(settings.MEDIA_ROOT, project.name)
            os.makedirs(project_dir, exist_ok=True)

            ground_truth_path = save_uploaded_file(ground_truth, project_dir)
            test_data_dir_path = os.path.join(project_dir, 'test_data')
            os.makedirs(test_data_dir_path, exist_ok=True)
            save_uploaded_file(test_data_directory, test_data_dir_path, True)

            try:
                project.save()
            except IntegrityError:
                return render(request, 'register_project.html', {'form': form, 'error_message': 'A project with this name already exists.'})

            if not check_table_exists(project.name):
                create_dynamic_model_from_excel(ground_truth_path, project.name)

            # Reload the app config to ensure the new model is recognized
            reload_app_config('bills')

            # Populate the dynamic model with data from the Excel file
            populate_dynamic_model_from_excel(ground_truth_path, project.name, check_table_exists(project.name))

            # Create dynamic model for the results table
            create_dynamic_results_model(project)  # Pass the Project instance

            return render(request, 'upload_success.html', {'message': 'Project registered successfully.', 'file_name': project.name})

    else:
        form = ProjectForm()

    return render(request, 'register_project.html', {'form': form})



def save_uploaded_file(uploaded_file, destination_path, extract_zip=False):
    file_path = os.path.join(destination_path, uploaded_file.name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with default_storage.open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    logger.info(f"File saved to {file_path}")

    if extract_zip and file_path.endswith('.zip'):
        shutil.unpack_archive(file_path, destination_path)
        os.remove(file_path)  # Clean up the temporary zip file

    return file_path

def create_dynamic_model_from_excel(excel_path, table_name):
    df = pd.read_excel(excel_path)
    columns = df.columns.tolist()

    class Meta:
        app_label = 'bills'

    attrs = {'__module__': 'bills.models', 'Meta': Meta}
    for column in columns:
        if column != 'id':  # Avoid duplicating the 'id' column
            attrs[column] = models.CharField(max_length=255, blank=True, null=True)

    DynamicModel = type(table_name, (models.Model,), attrs)
    app_config = apps.get_app_config('bills')
    app_config.models[table_name.lower()] = DynamicModel

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(DynamicModel)


def populate_dynamic_model_from_excel(excel_path, table_name, model_exists):
    df = pd.read_excel(excel_path)
    Model = apps.get_model('bills', table_name)
    instances = [Model(**row) for row in df.to_dict(orient='records')]
    Model.objects.bulk_create(instances)


from django.db import models, connection, IntegrityError
from django.apps import apps
from django.utils.module_loading import import_module

def create_dynamic_results_model(project):
    try:
        table_name = f'{project.name}_result'
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            if not cursor.fetchone():
                ground_truth_model = apps.get_model('bills', project.name)
                attrs = {field.name: models.CharField(max_length=255, blank=True, null=True) for field in ground_truth_model._meta.fields if field.name != 'id'}
                attrs['accuracy'] = models.FloatField(null=True)
                attrs['Meta'] = type('Meta', (), {'db_table': table_name})

                # Add module attribute to the attrs dictionary
                attrs['__module__'] = ground_truth_model.__module__

                model = type(table_name, (models.Model,), attrs)
                app_label = 'bills'
                app_config = apps.get_app_config(app_label)
                if table_name.lower() not in app_config.models:
                    app_config.models[table_name.lower()] = model
                    with connection.schema_editor() as schema_editor:
                        schema_editor.create_model(model)
                
                # Reload app config to recognize new model
                import_module(app_config.name)
                app_config = apps.get_app_config(app_label)
                logger.info(f"Successfully created dynamic model {table_name}")
            else:
                logger.info(f"Table {table_name} already exists")
    except Exception as e:
        logger.error(f"Error creating dynamic model for {project.name}: {e}")
        raise



def reload_app_config(app_label):
    app_config = apps.get_app_config(app_label)
    app_config.models_module = None
    app_config.import_models()
    for model in app_config.get_models():
        apps.register_model(app_label, model)

def check_table_exists(table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        return cursor.fetchone() is not None

def start_newtest(request):
    if request.method == 'GET':
        project_name = request.GET.get('project')
        if project_name:
            project = Project.objects.get(name=project_name)
            test_data_dir = os.path.join(settings.MEDIA_ROOT, project.name, 'test_data')
            results = []

            for filename in os.listdir(test_data_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_path = os.path.join(test_data_dir, filename)
                    # Construct request body
                    with open(image_path, "rb") as file:
                        image_file = file.read()
                        base64_string = base64.b64encode(image_file).decode('ascii')
                        body = {
                            "image_id": '123',
                            "image_content": base64_string
                        }

                        response = requests.post(project.api_url, json=body)
                        if response.status_code == 200:
                            # Parse the response JSON
                            result = response.json()
                            # Extract relevant data
                            result['image_name'] = filename  # Ensure image_name is included
                            results.append(result)

            results_table_name = f'{project.name}_result'
            create_results_table_and_populate(project, results_table_name, results)
            
            # Pretty print the JSON responses for better readability
            pretty_responses = [json.dumps(result, indent=4) for result in results]
            for pretty_response in pretty_responses:
                print(pretty_response)

            reload_app_config('bills')

            return redirect('current_result', project_id=project.id)

    projects = Project.objects.all()
    return render(request, 'choose_test.html', {'projects': projects})

def create_results_table_and_populate(project, table_name, results):
    if not results:
        logger.error("No results to populate.")
        return

    try:
        app_label = 'bills'
        app_config = apps.get_app_config(app_label)

        # Ensure the table is created based on ground truth structure
        if table_name.lower() not in app_config.models:
            create_dynamic_results_model(project.name)

        # Load ground truth data from the database
        ground_truth_df = pd.read_sql(f'SELECT * FROM bills_{project.name}', connection)

        # Define model fields based on the ground truth table columns
        ground_truth_columns = list(ground_truth_df.columns) + ['accuracy']
        fields = {column: models.CharField(max_length=255) for column in ground_truth_columns}
        fields_dict = {'__module__': 'bills.models'}
        fields_dict.update(fields)
        
        model_name = table_name
        model = type(model_name, (models.Model,), fields_dict)
        
        if model_name.lower() not in app_config.models:
            app_config.models[model_name.lower()] = model
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(model)

        # Populate the table with results data and calculate accuracy
        Model = apps.get_model('bills', table_name)
        instances = []
        for result in results:
            # Comparison with ground truth
            image_name = result['image_name']
            ground_truth_rows = ground_truth_df[ground_truth_df['image_name'] == image_name].to_dict(orient='records')
            if not ground_truth_rows:
                logger.warning(f"No ground truth data found for image: {image_name}")
                continue

            ground_truth_row = ground_truth_rows[0]

            correct_cells = 0
            total_cells = 0
            for key in ground_truth_columns:
                if key in result and key in ground_truth_row:
                    total_cells += 1
                    if str(result[key]).strip().lower() == str(ground_truth_row[key]).strip().lower():
                        correct_cells += 1

            percentage_correct = (correct_cells / total_cells) * 100 if total_cells > 0 else 0
            result['accuracy'] = percentage_correct
            instances.append(Model(**result))

        Model.objects.bulk_create(instances)
        logger.info(f"Successfully populated table {table_name}")

    except Exception as e:
        logger.error(f"Error creating and populating table {table_name}: {e}")
        raise



from django.db.utils import ProgrammingError

def view_current_result(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    results_table_name = f'{project.name}_result'
    ResultsModel = apps.get_model('bills', results_table_name)

    try:
        results = ResultsModel.objects.all()
    except ProgrammingError as e:
        if 'Table' in str(e) and 'does not exist' in str(e):
            create_dynamic_results_model(project.name)
            ResultsModel = apps.get_model('bills', results_table_name)
            results = ResultsModel.objects.all()
        else:
            raise e
    
    ground_truth_df = pd.read_sql(f'SELECT * FROM bills_{project.name}', connection)
    comparison_results = []
    for result in results:
        result_dict = result.__dict__
        image_name = result_dict['image_name']
        ground_truth_rows = ground_truth_df[ground_truth_df['image_name'] == image_name].to_dict(orient='records')
        if not ground_truth_rows:
            logger.warning(f"No ground truth data found for image: {image_name}")
            continue

        ground_truth_row = ground_truth_rows[0]
        comparison = {}
        for key in result_dict:
            if key not in ['_state', 'id']:
                ground_truth_value = ground_truth_row.get(key)
                api_result_value = result_dict[key]
                comparison[key] = {
                    'api_result': api_result_value,
                    'ground_truth': ground_truth_value,
                    'match': api_result_value == ground_truth_value
                }

        comparison_results.append({
            'image_name': image_name,
            'comparison': comparison,
            'accuracy': result_dict['accuracy']  # include the calculated accuracy
        })
    
    return render(request, 'current_result.html', {
        'project_name': project.name,
        'comparison_results': comparison_results,
    })


def calculate_accuracy(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    results_table_name = f'{project.name}_result'
    ResultsModel = apps.get_model('bills', results_table_name)
    
    ground_truth_df = pd.read_sql(f'SELECT * FROM bills_{project.name}', connection)
    
    for result in ResultsModel.objects.all():
        result_dict = result.__dict__
        image_name = result_dict['image_name']
        ground_truth_rows = ground_truth_df[ground_truth_df['image_name'] == image_name].to_dict(orient='records')
        if not ground_truth_rows:
            logger.warning(f"No ground truth data found for image: {image_name}")
            continue

        ground_truth_row = ground_truth_rows[0]
        correct_cells = 0
        total_cells = 0
        for key in ground_truth_row:
            if key in result_dict and key in ground_truth_row:
                total_cells += 1
                if str(result_dict[key]).strip().lower() == str(ground_truth_row[key]).strip().lower():
                    correct_cells += 1

        percentage_correct = (correct_cells / total_cells) * 100 if total_cells > 0 else 0
        result.accuracy = percentage_correct
        result.save()
    
    return redirect('current_result', project_id=project.id)

