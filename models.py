
from django.db import models

class Invoice(models.Model):
    test_id = models.CharField(max_length=255, null=True)
    invoice_number = models.CharField(max_length=255, null=True)
    buyer_name = models.CharField(max_length=255, null=True)
    buyer_address = models.CharField(max_length=255, null=True)
    due_date = models.CharField(max_length=10, null=True)  # Changed to CharField
    invoice_date = models.CharField(max_length=10, null=True)  # Changed to CharField
    total = models.CharField(max_length=50, null=True)
    seller_name = models.CharField(max_length=255, null=True)
    seller_address = models.CharField(max_length=255, null=True)
    tax = models.CharField(max_length=50, blank=True, null=True)
    discount = models.CharField(max_length=50, blank=True, null=True)
    payment_details = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=3, null=True)
    image_name = models.CharField(max_length=255, null=True)
    expected_result = models.CharField(max_length=255, null=True)
    
    image_path = models.CharField(max_length=255, null =True)
    
    def generate_test_id():
        last_test = Invoice.objects.order_by('-id').first()
        if last_test:
            last_test_id = last_test.test_id
            if last_test_id.startswith("Test "):
                test_number = int(last_test_id.split(" ")[1]) + 1
                return f"Test {test_number}"
        return "Test 1"
    


class ExcelData(models.Model):
    invoice_number = models.CharField(max_length=255, null=True)
    buyer_name = models.CharField(max_length=255, null=True)
    buyer_address = models.CharField(max_length=255, null=True)
    due_date = models.CharField(max_length=255, null=True)  # Changed to CharField
    invoice_date = models.CharField(max_length=255, null=True)  # Changed to CharField
    total = models.CharField(max_length=255, null=True)
    seller_name = models.CharField(max_length=255, null=True)
    seller_address = models.CharField(max_length=255, null=True)
    tax = models.CharField(max_length=255, blank=True, null=True)
    discount = models.CharField(max_length=255, blank=True, null=True)
    payment_details = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=255, null=True)
    image_name = models.CharField(max_length=255, null=True)
    item_description = models.CharField(max_length=255, null=True)
    test_id = models.CharField(max_length=255, null=True)
    expected_result = models.CharField(max_length=255, null=True)

    
    
class LineItem(models.Model):
    invoice_number = models.CharField(max_length=255)
    item_description = models.CharField(max_length=255)
    unit_price = models.CharField(max_length=50)  #models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.CharField(max_length=50) #quantity = models.IntegerField()
    amount = models.CharField(max_length=50) #DecimalField(max_digits=10, decimal_places=2)


class uploadedInvoice(models.Model) :
    invoice_number = models.CharField(max_length=255, null=True)
    buyer_name = models.CharField(max_length=255, null=True)
    buyer_address = models.CharField(max_length=255, null=True)
    due_date = models.CharField(max_length=10, null=True)  # Changed to CharField
    invoice_date = models.CharField(max_length=10, null=True)  # Changed to CharField
    total = models.CharField(max_length=50, null=True)
    seller_name = models.CharField(max_length=255, null=True)
    seller_address = models.CharField(max_length=255, null=True)
    tax = models.CharField(max_length=50, blank=True, null=True)
    discount = models.CharField(max_length=50, blank=True, null=True)
    payment_details = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=3, null=True)

    def __str__(self):
        return self.invoice_number
    


from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=255, null=True, unique=True)
    api_url = models.URLField()
    ground_truth_file = models.CharField(max_length=255, null=True)
    test_data_directory = models.CharField(max_length=255, null=True)

    def __str__(self):
        return self.name
