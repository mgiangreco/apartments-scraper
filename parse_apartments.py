import boto3
import csv
import datetime
import json
import re
import sys
import datetime
import requests
import os
from bs4 import BeautifulSoup

# Config parser was renamed in Python 3
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

def create_csv(search_urls, fname):
    """Create a CSV file with information that can be imported into ideal-engine"""

    # avoid the issue on Windows where there's an extra space every other line
    if sys.version_info[0] == 2:  # Not named on 2.6
        access = 'wb'
        kwargs = {}
    else:
        access = 'wt'
        kwargs = {'newline': ''}
    # open file for writing
    csv_file = open(fname, access, **kwargs)

    # write to CSV
    try:
        writer = csv.writer(csv_file)
        # this is the header (make sure it matches with the fields in
        # write_parsed_to_csv)
        header = ['Option Name', 'Contact', 'Address', 'Size',
                  'Rent', 'Monthly Fees', 'One Time Fees',
                  'Pet Policy', 
                  'Parking', 'Gym', 'Kitchen',
                  'Amenities', 'Features', 'Living Space',
                  'Lease Info', 'Services',
                  'Property Info', 'Indoor Info', 'Outdoor Info',
                  'Images', 'Description', 'ds']

        # write the header
        writer.writerow(header)

        # parse current entire apartment list including pagination for all search urls
        for url in search_urls:
            print ("Now getting apartments from: %s" % url)
            write_parsed_to_csv(url, writer)

    finally:
        csv_file.close()


def write_parsed_to_csv(page_url, writer):
    """Given the current page URL, extract the information from each apartment in the list"""

    # read the current page
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
    page = requests.get(page_url, headers=headers)
 
    # soupify the current page
    soup = BeautifulSoup(page.content, 'html.parser')
    soup.prettify()
    # only look in this region
    soup = soup.find('div', class_='placardContainer')

    # append the current apartments to the list
    for item in soup.find_all('article', class_='placard'):
        url = ''
        rent = ''
        contact = ''

        if item.find('a', class_='placardTitle') is None: continue
        url = item.find('a', class_='placardTitle').get('href')

        # get the rent and parse it to unicode
        obj = item.find('span', class_='altRentDisplay')
        if obj is not None:
            rent = obj.getText().strip()

        # get the phone number and parse it to unicode
        obj = item.find('div', class_='phone')
        if obj is not None:
            contact = obj.getText().strip()

        # get the other fields to write to the CSV
        fields = parse_apartment_information(url)

        # make this wiki markup
        fields['name'] = '[' + str(fields['name']) + '](' + url + ')'
        fields['address'] = '[' + fields['address'] + '](' + ')'

        # get the datetime
        fields['ds'] = str(datetime.datetime.utcnow().date())

        # fill out the CSV file
        row = [fields['name'], contact,
               fields['address'], fields['size'],
               rent, fields['monthFees'], fields['onceFees'],
               fields['petPolicy'], 
               fields['parking'], fields['gym'], fields['kitchen'],
               fields['amenities'], fields['features'], fields['space'],
               fields['lease'], fields['services'],
               fields['info'], fields['indoor'], fields['outdoor'],
               fields['img'], fields['description'], fields['ds']]
        # write the row
        writer.writerow(row)

    # get the next page URL for pagination
    next_url = soup.find('a', class_='next')

    # if there's only one page this will actually be none
    if next_url is None:
        return

    # get the actual next URL address
    next_url = next_url.get('href')

    if next_url is None or next_url == '' or next_url == 'javascript:void(0)':
        return

    # recurse until the last page
    write_parsed_to_csv(next_url, writer)


def parse_apartment_information(url):
    """For every apartment page, populate the required fields to be written to CSV"""

    # read the current page
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
    page = requests.get(url, headers=headers)

    # soupify the current page
    soup = BeautifulSoup(page.content, 'html.parser')
    soup.prettify()

    # the information we need to return as a dict
    fields = {}

    # get the name of the property
    get_property_name(soup, fields)

    # get the address of the property
    get_property_address(soup, fields)

    # get the size of the property
    get_property_size(soup, fields)

    # get the one time and monthly fees
    get_fees(soup, fields)

    # get the images as a list
    get_images(soup, fields)

    # get the description section
    get_description(soup, fields)

    # only look in this section (other sections are for example for printing)
    soup = soup.find('section', class_='specGroup js-specGroup')

    # get the pet policy of the property
    get_pet_policy(soup, fields)

    # get parking information
    get_parking_info(soup, fields)

    # get the amenities description
    get_field_based_on_class(soup, 'amenities', 'featuresIcon', fields)

    # get the 'interior information'
    get_field_based_on_class(soup, 'indoor', 'interiorIcon', fields)

    # get the 'outdoor information'
    get_field_based_on_class(soup, 'outdoor', 'parksIcon', fields)

    # get the 'gym information'
    get_field_based_on_class(soup, 'gym', 'fitnessIcon', fields)

    # get the 'kitchen information'
    get_field_based_on_class(soup, 'kitchen', 'kitchenIcon', fields)

    # get the 'services information'
    get_field_based_on_class(soup, 'services', 'servicesIcon', fields)

    # get the 'living space information'
    get_field_based_on_class(soup, 'space', 'sofaIcon', fields)

    # get the lease length
    get_field_based_on_class(soup, 'lease', 'leaseIcon', fields)

    # get the 'property information'
    get_features_and_info(soup, fields)

    return fields

def prettify_text(data):
    """Given a string, replace unicode chars and make it prettier"""

    # format it nicely: replace multiple spaces with just one
    data = re.sub(' +', ' ', data)
    # format it nicely: replace multiple new lines with just one
    data = re.sub('(\r?\n *)+', '\n', data)
    # format it nicely: replace bullet with *
    data = re.sub(u'\u2022', '* ', data)
    # format it nicely: replace registered symbol with (R)
    data = re.sub(u'\xae', ' (R) ', data)
    # format it nicely: remove trailing spaces
    data = data.strip()
    # format it nicely: encode it, removing special symbols
    data = data.encode('utf8', 'ignore')

    return str(data).encode('utf-8')


def get_images(soup, fields):
    """Get the images of the apartment"""

    fields['img'] = ''

    if soup is None: return

    # find ul with id fullCarouselCollection
    soup = soup.find('ul', {'id': 'fullCarouselCollection'})
    if soup is not None:
        for img in soup.find_all('img'):
            fields['img'] += '![' + img['alt'] + '](' + img['src'] + ') '

def get_description(soup, fields):
    """Get the description for the apartment"""

    fields['description'] = ''

    if soup is None: return

    # find p with itemprop description
    obj = soup.find('p', {'itemprop': 'description'})

    if obj is not None:
        fields['description'] = prettify_text(obj.getText())

def get_property_size(soup, fields):
    """Given a beautifulSoup parsed page, extract the property size of the first one bedroom"""
    #note: this might be wrong if there are multiple matches!!!

    fields['size'] = ''

    if soup is None: return
    
    obj = soup.find('tr', {'data-beds': '1'})
    if obj is not None:
        data = obj.find('td', class_='sqft').getText()
        data = prettify_text(data)
        fields['size'] = data


def get_features_and_info(soup, fields):
    """Given a beautifulSoup parsed page, extract the features and property information"""

    fields['features'] = ''
    fields['info'] = ''

    if soup is None: return
    
    obj = soup.find('i', class_='propertyIcon')

    if obj is not None:
        for obj in soup.find_all('i', class_='propertyIcon'):
            data = obj.parent.findNext('ul').getText()
            data = prettify_text(data)

            if obj.parent.findNext('h3').getText().strip() == 'Features':
                # format it nicely: remove trailing spaces
                fields['features'] = data
            if obj.parent.findNext('h3').getText() == 'Property Information':
                # format it nicely: remove trailing spaces
                fields['info'] = data


def get_field_based_on_class(soup, field, icon, fields):
    """Given a beautifulSoup parsed page, extract the specified field based on the icon"""

    fields[field] = ''

    if soup is None: return
    
    obj = soup.find('i', class_=icon)
    if obj is not None:
        data = obj.parent.findNext('ul').getText()
        data = prettify_text(data)

        fields[field] = data


def get_parking_info(soup, fields):
    """Given a beautifulSoup parsed page, extract the parking details"""

    fields['parking'] = ''

    if soup is None: return
    
    obj = soup.find('div', class_='parkingDetails')
    if obj is not None:
        data = obj.getText()
        data = prettify_text(data)

        # format it nicely: remove trailing spaces
        fields['parking'] = data


def get_pet_policy(soup, fields):
    """Given a beautifulSoup parsed page, extract the pet policy details"""
    if soup is None:
        fields['petPolicy'] = ''
        return
    
    # the pet policy
    data = soup.find('div', class_='petPolicyDetails')
    if data is None:
        data = ''
    else:
        data = data.getText()
        data = prettify_text(data)

    # format it nicely: remove the trailing whitespace
    fields['petPolicy'] = data


def get_fees(soup, fields):
    """Given a beautifulSoup parsed page, extract the one time and monthly fees"""

    fields['monthFees'] = ''
    fields['onceFees'] = ''

    if soup is None: return

    obj = soup.find('div', class_='monthlyFees')
    if obj is not None:
        for expense in obj.find_all('div', class_='fee'):
            description = expense.find(
                'div', class_='descriptionWrapper').getText()
            description = prettify_text(description)

            price = expense.find('div', class_='priceWrapper').getText()
            price = prettify_text(price)

            fields['monthFees'] += '* ' + description + ': ' + price + '\n'

    # get one time fees
    obj = soup.find('div', class_='oneTimeFees')
    if obj is not None:
        for expense in obj.find_all('div', class_='fee'):
            description = expense.find(
                'div', class_='descriptionWrapper').getText()
            description = prettify_text(description)

            price = expense.find('div', class_='priceWrapper').getText()
            price = prettify_text(price)

            fields['onceFees'] += '* ' + description + ': ' + price + '\n'

    # remove ending \n
    fields['monthFees'] = fields['monthFees'].strip()
    fields['onceFees'] = fields['onceFees'].strip()

def average_field(obj1, obj2, field):
    """Take the average given two objects that have field values followed by (same) unit"""
    val1 = float(prettify_text(obj1[field]).split()[0])
    val2 = float(prettify_text(obj2[field]).split()[0])
    unit = ' ' + prettify_text(obj1[field]).split()[1]

    avg = 0.5 * (val1 + val2)
    if field == 'duration':
        avg = int(avg)

    return str(avg) + unit

def get_property_name(soup, fields):
    """Given a beautifulSoup parsed page, extract the name of the property"""
    fields['name'] = ''

    # get the name of the property
    obj = soup.find('h1', class_='propertyName')
    if obj is not None:
        name = obj.getText()
        name = prettify_text(name)
        fields['name'] = name

def find_addr(script, tag):
    """Given a script and a tag, use python find to find the text after tag"""

    tag = tag + ": \'"
    start = script.find(tag)+len(tag)
    end = script.find("\',", start)
    return script[start : end]

def get_property_address(soup, fields):
    """Given a beautifulSoup parsed page, extract the full address of the property"""

    address = ""

    # They changed how this works so I need to grab the script
    script = soup.findAll('script', type='text/javascript')[2].text
    
    # The address is everything in quotes after listingAddress
    address = find_addr(script, "listingAddress")

    # City
    address += ", " + find_addr(script, "listingCity")

    # State
    address += ", " + find_addr(script, "listingState")

    # Zip Code
    address += " " + find_addr(script, "listingZip")

    fields['address'] = address


def parse_config_times(given_time):
    """Convert the tomorrow at given_time New York time to seconds since epoch"""

    # tomorrow's date
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    # tomorrow's date/time string based on time given
    date_string = str(tomorrow) + ' ' + given_time
    # tomorrow's datetime object
    format_ = '%Y-%m-%d %I:%M %p'
    date_time = datetime.datetime.strptime(date_string, format_)

    # the epoch
    epoch = datetime.datetime.utcfromtimestamp(0)

    # return time since epoch in seconds, string without decimals
    time_since_epoch = (date_time - epoch).total_seconds()
    return str(int(time_since_epoch))

def save_file_to_s3(bucket, fname):
    s3 = boto3.resource('s3')        
    data = open(fname, 'rb')
    s3.Bucket(bucket).put_object(Key=fname, Body=data)

def main():
    """Read from the config file"""

    conf = configparser.ConfigParser()
    config_file = os.path.join(os.path.dirname(__file__), "config.ini")
    conf.read(config_file)

    # get the apartments.com search URL(s)
    apartments_url_config = conf.get('all', 'apartmentsURL')
    urls = apartments_url_config.replace(" ", "").split(",")

    # get the name of the output file
    fname = conf.get('all', 'fname') + '.csv'

    create_csv(urls, fname)

    save_file_to_s3('mg-apartments', fname)


if __name__ == '__main__':
    main()
