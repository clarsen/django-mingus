from django.utils import simplejson
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from basic.blog.models import Post, Category
from django.conf import settings
from django import http
from django.template import loader, Context
from django_proxy.models import Proxy
from django.views.generic import list_detail
from basic.blog.models import Settings
from view_cache_utils import cache_page_with_prefix
from contact_form.views import contact_form as django_contact_form
from contact_form.forms import ContactForm
from honeypot.decorators import check_honeypot
from tagging.models import Tag, TaggedItem
from django.shortcuts import render_to_response
from django.template import RequestContext

def page_key_prefix(request):
    '''Used by cache_page_with_prefix to create a cache key prefix.'''
    return request.GET.get('page','')


def build_url(domainname):
    '''Given a domain name (ex mywebsite.com) it returns the full url.'''
    return 'http://%s' % domainname


def post_result_item(post):
    '''Generates the item result object for django-springsteen integration.'''
    return {
        'title': post.title,
        'url': build_url(Settings.get_current().site.domain) + post.get_absolute_url(),
        'text': post.body,
        }

def springsteen_results(request):
    '''
    Creates the django-springsteen compliant JSON results for only for findjango
    integration.

    Results:
        Published Post objects.
    '''

    results = [ post_result_item(item) for item in Post.objects.published()[:50] ]
    response_dict = { 'total_results': Post.objects.published().count(),
                    'results': results, }
    return HttpResponse(simplejson.dumps(response_dict), mimetype='application/javascript')


def server_error(request, template_name='500.html'):
    '''Handles displaying 500 server error page along with application MEDIA.'''

    t = loader.get_template(template_name)
    blog_settings = Settings.get_current()

    return http.HttpResponseServerError(t.render(Context({
        "MEDIA_URL": settings.MEDIA_URL,
        "STATIC_URL": settings.STATIC_URL,
        "BLOG_SETTINGS": blog_settings,
    })))

def springsteen_firehose(request):
    '''
    Generates django-springsteen compliant JSON results of proxy models for
    findjango integration.

    '''

    def result_item(proxy):
        '''Generates the item result object.'''

        if proxy.content_type.name == 'bookmark':
            url = proxy.content_object.get_absolute_url()
        else:
            url = build_url(Settings.get_current().site.domain) + proxy.content_object.get_absolute_url()

        return {
            'title': proxy.title,
            'url': url,
            'text': proxy.description,
            }

    posts = Proxy.objects.published().order_by('-pub_date')[:50]
    results = [ result_item(item) for item in posts ]
    response_dict = { 'total_results': Proxy.objects.published().count(),
                    'results': results, }
    return HttpResponse(simplejson.dumps(response_dict), mimetype='application/javascript')

def springsteen_category(request, slug):
    '''
    Creates the django-springsteen compliant JSON results for only for
    findjango integration.

    Results:
        Published Post objects by category.
    '''

    category = get_object_or_404(Category, slug__iexact=slug)
    posts = category.post_set.published()[:50]
    results = [ post_result_item(item) for item in posts ]
    response_dict = { 'total_results': category.post_set.published().count(),
                    'results': results, }
    return HttpResponse(simplejson.dumps(response_dict),
                        mimetype='application/javascript')


@cache_page_with_prefix(60, page_key_prefix)
def home_list(request, page=0, template_name='proxy/proxy_list_front.html', **kwargs):
    '''
    Homepage.

    Template: ``proxy/proxy_list_front.html``
    Context:
        object_list
            Aggregated list of Proxy instances (post, quote, bookmark).

    '''

    posts = Proxy.objects.published().order_by('-pub_date')
    pagesize = Settings.get_current().page_size or 20

    return list_detail.object_list(
        request,
        queryset = posts,
        paginate_by = pagesize,
        page = page,
        template_name = template_name,
        **kwargs
    )


def tag_detail(request, slug, template_name='proxy/tag_detail.html', **kwargs):
    ''' Display objects for all content types supported: Post and Quotes.'''

    tag = get_object_or_404(Tag, name__iexact=slug)

    #below could be prettier
    results = []
    qs = Proxy.objects.published().filter(tags__icontains=tag.name).order_by('-pub_date')
    for item in qs:
        comma_delimited = (',' in item.tags)
        if comma_delimited:
            for t in item.tags.split(','):
                if t.strip(' ') == tag.name:
                    results.append(item)
        else:
            for t in item.tags.split(' '):
                if t.strip(' ') == tag.name:
                    results.append(item)

    return render_to_response(template_name,
                    {'tag': tag, 'object_list': results},
                    context_instance=RequestContext(request),
                    )

@check_honeypot
def contact_form(request, form_class=ContactForm,
                 template_name='contact_form/contact_form.html'):

    '''
    Handles the contact form view. Leverages django-contact-form.

    This is an example of overriding another reusable apps view. This particular
    view also contains a form. For this example we are just doing the basic
    implementation by wrapping the view function and simply passing the
    arguments along.

    This view is also leveraging another reusable app, django-honeypot. The
    decorator you see being applied is used to protect your app from spam.
    '''
    return django_contact_form(request, form_class=form_class,
                 template_name=template_name)
