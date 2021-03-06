from django.shortcuts import render, get_object_or_404, get_list_or_404, redirect
from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from ..models import *


def resolve_voice_labels(choice_options, language):
    """
    Returns a list of voice labels belonging to the provided list of choice_options.
    """
    if(choice_options):
        voice_labels = []
        for choice_option in choice_options:
            voice_labels.append(choice_option.get_voice_fragment_url(language))
        return voice_labels

    return


def get_model_from_any_app(model_name):

    for app_config in apps.get_app_configs():
        try:
            model = app_config.get_model(model_name)
            return model
        except LookupError:
            pass
    return None


def choice_generate_context(choice_element, session, element_id):
    """
    Returns a dict that can be used to generate the choice VXML template
    choice = this Choice element object
    choice_voice_label = the resolved Voice Label URL for this Choice element
    choice_options = iterable of ChoiceOption object belonging to this Choice element
    choice_options_voice_labels = list of resolved Voice Label URL's referencing to the choice_options in the same position
    choice_options_redirect_urls = list of resolved redirection URL's referencing to the choice_options in the same position
        """
    model_type = choice_element.model_type
    action = choice_element.action_type
    model = get_model_from_any_app(model_type)
    farmer = session.farmer
    advertisements = Advertisement.objects.filter(farmer=farmer)

    choice_elements = None
    if action == 'create' and advertisements:
        for item in advertisements.values(model_type):
            choice_elements = model.objects.exclude(id=item[model_type])
    elif (action == 'update' or action == 'remove') and advertisements:
        for item in advertisements.values(model_type):
            choice_elements = model.objects.filter(id=item[model_type])
    elif action == 'create':
        choice_elements = model.objects.all()

    language = session.language

    redirect_url_POST = reverse('service-development:form-choice', args=[element_id, session.id])

    pass_on_variables = {
        'redirect_url': choice_element.redirect.get_absolute_url(session),
        'action': action
    }

    context = {
        'choice': choice_element,
        'choice_voice_label': choice_element.get_voice_fragment_url(language, choice_element.voice_label),
        'choice_options': choice_elements,
        'voice_labels': resolve_voice_labels(choice_elements, language),
        'redirect_url': redirect_url_POST,
        'pass_on_variables': pass_on_variables,
        'language': language,
        'no_items_voice_label': choice_element.get_voice_fragment_url(language, choice_element.no_items_voice_label),
        'go_back_redirect': reverse('service-development:voice-service', args= [element_id, session.id])
    }
    return context


def post(request, session, model_type):
    action = request.POST["action"]
    selection = request.POST["option_id"]
    item = get_model_from_any_app(model_type).objects.get(id=selection)

    if action == 'create':
        advertisement = Advertisement(farmer=session.farmer)
        setattr(advertisement, model_type, item)
        advertisement.save()
        session.link_to_advertisement(advertisement)
        session.replay_action_create.add(advertisement)
    elif action == 'update':
        advertisement = Advertisement.objects.get(**{model_type: item})
        CallSession.objects.filter(id=session.id).update(advertisement=advertisement)
        session.replay_action_update.add(advertisement)
    elif action == 'remove':
        advertisement = Advertisement.objects.get(**{model_type: item})
        session.replay_action_remove.add(advertisement)
        advertisement.delete()
        CallSession.objects.filter(id=session.id).update(advertisement=None)
    return


def form_choice(request, element_id, session_id):
    session = get_object_or_404(CallSession, pk=session_id)
    choice_element = get_object_or_404(FormChoice, pk=element_id)
    session.record_step(choice_element)
    model_type = choice_element.model_type

    if request.method == "POST":
        if 'redirect_url' in request.POST:
            redirect_url = request.POST['redirect_url']
        else: raise ValueError('Incorrect request, redirect_url not set')
        if 'option_id' not in request.POST:
            raise ValueError('Incorrect request, no option selected')
        if 'action' not in request.POST:
            raise ValueError('No action defined')

        post(request, session, model_type)

        return HttpResponseRedirect(redirect_url)

    elif request.method == "GET":
        context = choice_generate_context(choice_element, session, element_id)

        return render(request, 'form_choice.xml', context, content_type='text/xml')

