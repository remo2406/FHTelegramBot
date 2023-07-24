from socket import timeoutcom
import telebot
from telebot import types
import requests
import json
import time
import logging
import sqlite3
import pandas as pd
import db

# CONFIGURAÇÕES GERAIS
chave_api = '' # PREENCHER COM CHAVE OBTIDA NO BOTFATHER
bot = telebot.TeleBot(chave_api)

senhaautorizacao = '' # DEFINIR DE ACORDO COM PREFERENCIA
nomeempresa = '' # DEFINIR DE ACORDO COM PREFERENCIA
manutencao = False # DEFINIR PARA True CASO REALIZE MANUTENÇÃO E NÃO QUEIRA DESATIVAR A APLICAÇÃO
chatidgrupodeavisos = int # CRIE UM GRUPO PARA ENVIAR OS AVISOS DE ONU'S LIBERADAS FORA DO PADRÃO

url_api = '' # DEFINA A URL DA API DO TL1
iptl1 = ''
portatl1 = ''
usuariounm = ''
senhaunm = ''

# LISTA DE AUTORIZADOS
df = db.retornadadosdb()

autorizados = []
blacklist = []

for index, row in df.iterrows():
    if row['autorizado'] == 1:
        autorizados.append(row['user_id'])
    elif row['autorizado'] == 0:
        blacklist.append(row['user_id'])
    
# FUNÇÕES DE AUTORIZAR
@bot.message_handler(commands=['autorizar'])
def autorizacao(mensagem):

    try:
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
    except:
        print('Usuário sem sobrenome: '+mensagem.from_user.first_name)
        bot.send_message(mensagem.chat.id, 
                         "Não foi identificado sobrenome em sua conta Telegram."
                         "Por favor, acesse as configurações e adicione a informação no campo "
                         "'Sobrenome' para continuar as interações com o Bot :)")
        return
       
    bot.send_message(mensagem.chat.id, "Informe o código para liberação:")
    bot.register_next_step_handler(mensagem, autorizacao2)

def autorizacao2(mensagem):

    if mensagem.text == senhaautorizacao:
        user_id = mensagem.from_user.id
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
        autorizados.append(user_id)
        db.adicionarinfodb(user_id)

        bot.send_message(chatidgrupodeavisos, 
                         f"Favor adicionar o UserID {str(mensagem.from_user.id)} "
                         f"do usuário {nomeusuario} à lista de autorizados.")   
         
        bot.send_message(mensagem.chat.id, "Pronto! Acesso liberado.")
        return
    else:
        bot.send_message(mensagem.chat.id, "Código inválido! Finalizando seu contato.")
        return

# FUNÇÕES DE BLOQUEAR USUARIO
@bot.message_handler(commands=['bloquearusuario'])
def bloquearusuario(mensagem):
    bot.send_message(mensagem.chat.id, "Informe o UserID do usuário que deseja bloquear:")
    bot.register_next_step_handler(mensagem, bloquearusuario2)
    return

def bloquearusuario2(mensagem):
    user_id = mensagem.text
    info = db.alterarinfodb(user_id)
    blacklist.append(user_id)

    if info == 'Sucesso':
        bot.send_message(mensagem.chat.id, f"UserID {str(user_id)} bloqueado com sucesso!")
    else:
        bot.send_message(mensagem.chat.id, 
                         f"UserID {str(user_id)} não foi encontrado no Banco de Dados. Tente novamente...")
    return

# FUNÇÕES DE ENTRADA NO BOT
@bot.message_handler(commands=['start'])
def responder(mensagem):
    if mensagem.from_user.id in autorizados:
        try:
            nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
        except:
            print('Usuário sem sobrenome: '+mensagem.from_user.first_name)
            bot.send_message(mensagem.chat.id, 
                             "Não foi identificado sobrenome em sua conta Telegram. "
                             "Por favor, acesse as configurações e adicione a informação no campo "
                             "'Sobrenome' para continuar as interações com o Bot :)")
            return
        
        bot.reply_to(mensagem, f"Bem vindo ao Provisionamento {nomeempresa}!")
        print(nomeusuario+' '+str(mensagem.chat.id)+' iniciou uma interação')

        bot.send_message(mensagem.chat.id, 
        """Digite um dos seguintes comandos:
        /LiberarONU - Para provisionamento de ONU
        /ConsultarSinal - Para verificação de dB da ONU
        /AlterarModoOnu - Para alterar de Router para Bridge ou Bridge para Router
        /AutoProvisionar - Para provisionamento de ONU com configuração de timer""",
        reply_markup=types.ReplyKeyboardRemove())

    elif mensagem.from_user.id in blacklist:
        bot.send_message(mensagem.chat.id, "Você não possui autorização para interação com este bot!")
        return
    else:
        bot.send_message(mensagem.chat.id, 
                         "Você não possui autorização para interação"
                         " com este bot! Digite /autorizar para iniciar sua interação")
        return


# Função de para setar ip da OLT Escolhida
def ipsolts(nomeolt):
    
    if nomeolt == 'NOME OLT 1':
        ip_olt = 'IP OLT 1'
    elif nomeolt == 'NOME OLT 2':
        ip_olt = 'IP OLT 2'
    elif nomeolt == 'NOME OLT 3':
        ip_olt = 'IP OLT 3'
    return ip_olt
        
# Função para definir as VLANs
def definevlan(ip_olt, slot, pon):
    '''A configuração deste módulo dependerá de como as VLANS 
        estão configuradas em suas OLTS'''
    
    oltsslot1vlan1000 = [] # IPs das OLTS que começam no SLOT 1 e VLAN 1000
    oltsslot11vlan1000 = [] # IPs das OLTS que começam no SLOT 11 e VLAN 1000

    oltsslot1vlan100 = [] # IPs das OLTS que começam no SLOT 1 e VLAN 100
    oltsslot11vlan100 = [] # IPs das OLTS que começam no SLOT 1 e VLAN 100

    # EXEMPLO
    
    if ip_olt in oltsslot1vlan1000:
        if slot == 1:
            vlan = 1000+pon
    return vlan
    
        
#MÓDULO DE AUTOPROVISIONAMENTO COM TIMER
informaçõesautoprovisionar = {}

@bot.message_handler(commands=['AutoProvisionar'])
def autoprovisionar(mensagem):
    try:
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, 
                         "Não foi identificado sobrenome em sua conta Telegram. "
                         "Por favor, acesse as configurações e adicione a informação"
                         " no campo 'Sobrenome' para continuar as interações com o Bot :)")
        return

    informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario'] = nomeusuario


    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or mensagem.text == '/LiberarONU'):
        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return

    if mensagem.from_user.id in autorizados:
        
        print("Requisição de "+nomeusuario+" para Auto Provisionamento")
        if manutencao == True:
            bot.send_message(mensagem.chat.id, 
                             "Auto Provisionamento temporariamente suspenso." 
                             "Encaminhe sua liberação para o Grupo.")
            return
        bot.send_message(mensagem.chat.id, "Informe o MAC da ONU:")

        bot.register_next_step_handler(mensagem, macautprov)

    elif mensagem.from_user.id in blacklist:
        bot.send_message(mensagem.chat.id, "Você não possui autorização para interação com este bot!")
        return
    
    else:
        bot.send_message(mensagem.chat.id, 
                         "Você não possui autorização para interação "
                         "com este bot! Digite /autorizar para iniciar sua interação")
        return  
    

def macautprov(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU'
        or mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'
        or mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    mac_onu = mensagem.text.upper()
    if len(mac_onu) == 12 and mac_onu[:4] == 'FHTT':
        pass
    elif len(mac_onu) == 8:
        mac_onu = 'FHTT'+mac_onu
    else:
        bot.reply_to(mensagem, 'Opção inválida!')
        autoprovisionar(mensagem)
        return

    informaçõesautoprovisionar[str(mensagem.chat.id)+'mac'] = mac_onu

    markuptimer = types.ReplyKeyboardMarkup(one_time_keyboard=True)

    ummintimer = types.KeyboardButton("1 Minuto")
    doismintimer = types.KeyboardButton("2 Minutos")
    tresmintimer = types.KeyboardButton("3 Minutos")
    quatromintimer = types.KeyboardButton("4 Minutos")
    cincomintimer = types.KeyboardButton("5 Minutos")
    dezmintimer = types.KeyboardButton("10 Minutos")

    markuptimer.add(ummintimer)
    markuptimer.add(doismintimer)
    markuptimer.add(tresmintimer)
    markuptimer.add(quatromintimer)
    markuptimer.add(cincomintimer)
    markuptimer.add(dezmintimer)

    bot.send_message(mensagem.chat.id, "Informe o tempo que a ONU levará para pedir liberação:", reply_markup=markuptimer)
    bot.send_message(mensagem.chat.id, 
                     u"\uE252 Durante o período selecionado não deverão ser "
                     "realizadas interações comigo. Então, caso eu não responda, "
                     "aguarde a finalização do tempo informado ;)")

    bot.register_next_step_handler(mensagem, timerautprov)
    return

def timerautprov(mensagem):
    
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    timerdefinido = mensagem.text

    if timerdefinido[1] == ' ':
        timerdefinido = int(timerdefinido[0])
    else:
        timerdefinido = int(timerdefinido[:2])

    informaçõesautoprovisionar[str(mensagem.chat.id)+'timer'] = timerdefinido
    
    modelomarkup = types.ReplyKeyboardMarkup(one_time_keyboard=True)

    botaomini = types.KeyboardButton("ONU Mini")
    botaocomum1porta = types.KeyboardButton("ONU Comum 1 Porta")
    botaocomum2portas = types.KeyboardButton("ONU Comum 2 Portas")
    botaoonuwifi24 = types.KeyboardButton("ONU 2 Portas Wi-Fi 2.4GHz")
    botaoonuwifi5 = types.KeyboardButton("ONU 4 Portas Wi-Fi AC")

    modelomarkup.add(botaomini)
    modelomarkup.add(botaocomum1porta)
    modelomarkup.add(botaocomum2portas)
    modelomarkup.add(botaoonuwifi24)
    modelomarkup.add(botaoonuwifi5)

    bot.send_message(mensagem.chat.id, "Selecione se o modelo da ONU à ser liberada:",reply_markup=modelomarkup)

    bot.register_next_step_handler(mensagem, usuariopppoeautprov)
    return

def usuariopppoeautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    tipoonu = mensagem.text

    if tipoonu == "ONU Comum 2 Portas":
        tipoonu = 'AN5506-02-B'
    elif tipoonu == "ONU 2 Portas Wi-Fi 2.4GHz":
        tipoonu = 'AN5506-02-F'
    elif tipoonu == "ONU 4 Portas Wi-Fi AC":
        tipoonu = 'AN5506-04-FA'

    informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'] = tipoonu

    bot.send_message(mensagem.chat.id, "Informe o usuário PPPoE do cliente:")

    bot.register_next_step_handler(mensagem, nomeclientepppoeautprov)
    return

def nomeclientepppoeautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return

    informaçõesautoprovisionar[str(mensagem.chat.id)+'usuariopppoe'] = mensagem.text

    bot.send_message(mensagem.chat.id, "Informe o nome completo do cliente:")
    
    bot.register_next_step_handler(mensagem, nomeclienteautprov)
    return

def nomeclienteautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return

    informaçõesautoprovisionar[str(mensagem.chat.id)+'nomecliente'] = mensagem.text

    tipoonu = informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu']


    if tipoonu == 'AN5506-02-F' or tipoonu == 'AN5506-04-FA':
        tipoconexao = 'Router'
        informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'] = tipoconexao
    elif tipoonu == 'ONU Mini':
        tipoconexao = 'Bridge'
        informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'] = tipoconexao
    else:
        markupmodo = types.ReplyKeyboardMarkup(one_time_keyboard=True)

        markuprouter = types.KeyboardButton("Router")
        markupbridge = types.KeyboardButton("Bridge")

        markupmodo.add(markupbridge)
        markupmodo.add(markuprouter)

        bot.send_message(mensagem.chat.id, "Selecione o modo de configuração da ONU:",reply_markup=markupmodo)

        bot.register_next_step_handler(mensagem, modoonuautprov)
        return

    if tipoconexao == 'Router':
        bot.send_message(mensagem.chat.id, "Informe a senha PPPoE do cliente:", reply_markup=types.ReplyKeyboardRemove())

        bot.register_next_step_handler(mensagem, senhapppoeautprov)
        return
    elif tipoconexao == 'Bridge':
        aplicatimeronuautprov(mensagem)
        return

def modoonuautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return

    modoonu = mensagem.text
    informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'] = modoonu

    if modoonu == 'Bridge':
        aplicatimeronuautprov(mensagem)
        return

    elif modoonu == 'Router':
        bot.send_message(mensagem.chat.id, "Informe a senha PPPoE do cliente:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(mensagem, senhapppoeautprov)
        return

def senhapppoeautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return

    informaçõesautoprovisionar[str(mensagem.chat.id)+'senhapppoe'] = mensagem.text

    aplicatimeronuautprov(mensagem)
    return

def aplicatimeronuautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    timeraplic = informaçõesautoprovisionar[str(mensagem.chat.id)+'timer'] * 60
    timer = informaçõesautoprovisionar[str(mensagem.chat.id)+'timer']


    bot.send_message(mensagem.chat.id, "Tudo certo! Estarei aguardando por "+str(timer)+
                     " minuto(s). Caso a ONU não esteja pedindo liberação no momento informado, "
                     "o procedimento será encerrado e será necessário realizá-lo pelo módulo /LiberarONU"
                     ,reply_markup=types.ReplyKeyboardRemove())
    
    time.sleep(timeraplic)
    buscaonuautprov(mensagem)
    return

def buscaonuautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return

    bot.send_message(mensagem.chat.id, "Iniciando busca da ONU...")

    url = f'{url_api}/buscatodasOnus'
    
    data = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm
            }
    
    headers = {"Content-Type": "application/json"}
    request = requests.post(url, json=data, headers=headers)
    unregonus = json.loads(request.content)
    informaçõesautoprovisionar[str(mensagem.chat.id)+'listaonus'] = unregonus

    mac_onu = informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']
    informaçõesautoprovisionar[str(mensagem.chat.id)+'maccheck'] = ''
    for objeto in unregonus:
        if objeto['MAC'].upper() == mac_onu:
            informaçõesautoprovisionar[str(mensagem.chat.id)+'maccheck'] = objeto['MAC'].upper()
            informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'] = objeto['OLTID']
            informaçõesautoprovisionar[str(mensagem.chat.id)+'slot'] = objeto['SLOT']
            informaçõesautoprovisionar[str(mensagem.chat.id)+'pon'] = objeto['PON']
            informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon'] = objeto['SLOT']+'-'+objeto['PON']

    

    if informaçõesautoprovisionar[str(mensagem.chat.id)+'maccheck'] == mac_onu:
        bot.send_message(mensagem.chat.id, "ONU localizada! Iniciando liberação...")
        liberaonuautprov(mensagem)
        return
    else:
        bot.send_message(mensagem.chat.id, 
                         "ONU não localizada :( Verifique o equipamento "
                         "e tente realizar a liberação por /LiberarONU")
        print("Auto Provisionamento não concluído. MAC: "+mac_onu+". "
              "Requisição de",informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario'])
        return
    

def liberaonuautprov(mensagem, segundatentativa=False):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    ip_olt = informaçõesautoprovisionar[str(mensagem.chat.id)+'ip']
    slot = informaçõesautoprovisionar[str(mensagem.chat.id)+'slot']
    pon = informaçõesautoprovisionar[str(mensagem.chat.id)+'pon']

    vlan = str(definevlan(ip_olt, slot, pon))
    informaçõesautoprovisionar[str(mensagem.chat.id)+'vlan'] = vlan
    if informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'] == 'ONU Mini':
        data = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "ip_olt": informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'],
            "slot_pon": informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon'],
            "mac_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'mac'],
            "tipo_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'],
            "nome_cliente": informaçõesautoprovisionar[str(mensagem.chat.id)+'nomecliente'].upper(),
            "vlan": vlan,
            "tipo_conexao": informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'],
            "usuario_pppoe": informaçõesautoprovisionar[str(mensagem.chat.id)+'usuariopppoe'],
            "pass_pppoe": "101010"
            }

    elif (informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'] == 'ONU Comum 1 Porta' or 
          informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-B' or 
          informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-04-FA' or 
          informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-F'):
        
        if informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'ONU Comum 1 Porta':
            informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] = 'AN5506-01-A1'
        if informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'] == 'Router':
            data = {
                "ip_servidor_tl1": iptl1,
                "porta_servidor_tl1": portatl1,
                "usuario_anm": usuariounm,
                "senha_anm": senhaunm,
                "ip_olt": informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'],
                "slot_pon": informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon'],
                "mac_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'mac'],
                "tipo_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'],
                "nome_cliente": informaçõesautoprovisionar[str(mensagem.chat.id)+'nomecliente'].upper(),
                "vlan": vlan,
                "tipo_conexao": informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'],
                "usuario_pppoe": informaçõesautoprovisionar[str(mensagem.chat.id)+'usuariopppoe'],
                "pass_pppoe": informaçõesautoprovisionar[str(mensagem.chat.id)+'senhapppoe']
                }
        elif informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'] == 'Bridge':
            data = {
                "ip_servidor_tl1": iptl1,
                "porta_servidor_tl1": portatl1,
                "usuario_anm": usuariounm,
                "senha_anm": senhaunm,
                "ip_olt": informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'],
                "slot_pon": informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon'],
                "mac_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'mac'],
                "tipo_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu'],
                "nome_cliente": informaçõesautoprovisionar[str(mensagem.chat.id)+'nomecliente'].upper(),
                "vlan": vlan,
                "tipo_conexao": informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoconexao'],
                "usuario_pppoe": informaçõesautoprovisionar[str(mensagem.chat.id)+'usuariopppoe'],
                "pass_pppoe": "101010"
                }

    try:
        url = f'{url_api}/autorizaOnu'
        headers = {"Content-Type": "application/json"}
        request = requests.post(url, json=data, headers=headers)
        liberação = json.loads(request.content)

        informaçõesautoprovisionar[str(mensagem.chat.id)+'requestlib'] = liberação[0]['Request']
        
    except Exception as e:
        bot.send_message(mensagem.chat.id, "Ocorreu um erro para esta liberação :(")
        print(e)
        return
    tipoonu = informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu']


    if informaçõesautoprovisionar[str(mensagem.chat.id)+'requestlib'] == 'Sucesso':
        if tipoonu == 'AN5506-04-FA' or tipoonu == 'AN5506-02-F':
            bot.send_message(mensagem.chat.id, "Informe o Nome da Rede Wi-Fi (Máximo 32 caracteres):")
            
            bot.register_next_step_handler(mensagem, configuracaowifiautprov)
            return
        else:
            bot.send_message(mensagem.chat.id, "Liberação concluida! Iniciando análise de dB...")
            analisedbautprov(mensagem)
            return

    elif segundatentativa == False:
        liberaonuautprov(mensagem,segundatentativa=True)
        return
    else:
        bot.send_message(mensagem.chat.id, "Ocorreu um erro para esta liberação :(")
        print(e)
        return

def analisedbautprov(mensagem, count=0):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or
        mensagem.text == '/ConsultarSinal'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    vlan = informaçõesautoprovisionar[str(mensagem.chat.id)+'vlan']
    
    headers = {"Content-Type": "application/json"}
    urldb = f'{url_api}/consultaSinalOnu'
    datadb = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'],
        "slot_pon": informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon'],
        "mac_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']
    }
    
    
    requestdb = requests.post(urldb, json=datadb, headers=headers)
    consultadb = json.loads(requestdb.content)
    
    nomeonu = informaçõesautoprovisionar[str(mensagem.chat.id)+'usuariopppoe']+' - '
    +informaçõesautoprovisionar[str(mensagem.chat.id)+'nomecliente'].upper()
    print(consultadb)

    if consultadb != []:
        try:
            db = consultadb[0]['SINAL'].replace(',','.')
            db = float(db)
        except:
            db = 0.0

        if db != 0.0 and db != -40.0:
            if db < -26:
                print("Requisição realizada por "+informaçõesautoprovisionar[str(mensagem.chat.id)+
                     'nomeusuario']+"\nNome ONU: "+nomeonu+"\nMAC: "+informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']+
                     "\nOLT: "+informaçõesautoprovisionar[str(mensagem.chat.id)+'ip']+"\nSLOT-PON: "+
                     informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon']+"\nDB: "+str(db)+
                     "\nVLAN: "+vlan+"\nSTATUS: DESAUTORIZADA POR DB FORA DO PADRÃO")
                
                bot.send_message(chatidgrupodeavisos, "Alarme! ONU com dB "+str(db)+". Nome ONU: "+
                                 informaçõesautoprovisionar[str(mensagem.chat.id)+'nomecliente']+" MAC: "+
                                 informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']+". Requisição feita por "+
                                 informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario'])
                
                bot.send_message(mensagem.chat.id, "Cliente com dB "+str(db)+". Desautorizando ONU...")
                desautorizaonuautprov(mensagem)
                return
            else:
                print("Requisição realizada por "+informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario']+
                      "\nNome ONU: "+nomeonu+"\nMAC: "+informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']+
                      "\nOLT: "+informaçõesautoprovisionar[str(mensagem.chat.id)+'ip']+"\nSLOT-PON: "+
                      informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon']+"\nDB: "+str(db)+"\nVLAN: "+
                      vlan+"\nSTATUS: "+informaçõesautoprovisionar[str(mensagem.chat.id)+'requestlib'])
                
                bot.send_message(mensagem.chat.id, "ONU com dB "+str(db)+". Configuração finalizada!")
                return
            
        elif count == 8:
            bot.send_message(chatidgrupodeavisos, 
                             "Houve erro na consulta de dB da ONU "+informaçõesautoprovisionar[str(mensagem.chat.id)+
                             'mac']+". Requisição feita por "+informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario'])
            bot.send_message(mensagem.chat.id, 
                             "Liberação realizada com sucesso! Ocorreu um erro para consulta de dB, "
                             "mas estarei comunicando o setor de TI para análise.")
            print("Requisição realizada por "+informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario']+
                  "\nNome ONU: "+nomeonu+"\nMAC: "+informaçõesliberaonu[str(mensagem.chat.id)+'mac']+
                  "\nOLT: "+informaçõesliberaonu[str(mensagem.chat.id)+'ip']+"\nSLOT-PON: "+
                  informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon']+"\nDB: "+str(db)+
                  "\nVLAN: "+vlan+"\nSTATUS: "+informaçõesliberaonu[str(mensagem.chat.id)+'requestlib'])
            return
        
        else:
            count += 1
            time.sleep(10)
            analisedbautprov(mensagem, count=count)
            return

    elif count == 8:
        bot.send_message(chatidgrupodeavisos, 
                         "Houve erro na consulta de dB da ONU "+informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']+
                         ". Requisição feita por "+informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario'])
        bot.send_message(mensagem.chat.id, 
                         "Liberação realizada com sucesso! Ocorreu um erro para consulta de dB, "
                         "mas estarei comunicando o setor de TI para análise.")
        return
    
    else:
        count += 1
        time.sleep(10)
        analisedbautprov(mensagem, count=count)
        return

def desautorizaonuautprov(mensagem):
    mac_onu = informaçõesautoprovisionar[str(mensagem.chat.id)+'mac']
    slot_pon = informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon']

    headers = {"Content-Type": "application/json"}
    urldesautoriza = f'{url_api}/desautorizaOnu'
    datadesautoriza = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'],
        "slot_pon": slot_pon,
        "mac_onu": mac_onu
    }
    requestdesautoriza = requests.post(urldesautoriza, json=datadesautoriza, headers=headers)
    desautorizacao = json.loads(requestdesautoriza.content)

    if desautorizacao[0]['msg'] == 'Sucesso':
        bot.send_message(mensagem.chat.id, "ONU desautorizada! Entre em contato com o setor de TI para procedência do alarme.")
        bot.send_message(chatidgrupodeavisos, "ONU desautorizada!")
        return
    else:
        bot.send_message(chatidgrupodeavisos, "Erro na desautorização da ONU. Favor realizar desconfiguração manualmente.")
        return
        
def configuracaowifiautprov(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
    mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
    mensagem.text == '/ConsultarSinal'):
        
        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    nomewifi = mensagem.text
    informaçõesautoprovisionar[str(mensagem.chat.id)+'nomewifi'] = nomewifi
    bot.send_message(mensagem.chat.id, "Informe a senha do Wi-Fi (Mínimo 8 dígitos):")
    
    bot.register_next_step_handler(mensagem, configuracaowifi2autprov)
    return

def configuracaowifi2autprov(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    senhawifi = mensagem.text
    tipoonu = informaçõesautoprovisionar[str(mensagem.chat.id)+'tipoonu']

    bot.send_message(mensagem.chat.id, "Configurando o Wi-Fi...")
    urlconfig = f'{url_api}/configuraWiFi'
    headersconfig = {"Content-Type": "application/json"}
    dataconfig = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": informaçõesautoprovisionar[str(mensagem.chat.id)+'ip'],
        "mac_onu": informaçõesautoprovisionar[str(mensagem.chat.id)+'mac'],
        "slot_pon": informaçõesautoprovisionar[str(mensagem.chat.id)+'slot_pon'],
        "ssid_name": informaçõesautoprovisionar[str(mensagem.chat.id)+'nomewifi'],
        "preshared_key": senhawifi,
        "tipo_onu": tipoonu
    }
    requestconfig = requests.post(urlconfig, json=dataconfig, headers=headersconfig)
    configwifi = json.loads(requestconfig.content)
    if tipoonu == 'AN5506-04-FA' and configwifi[0]['Wi-Fi 2.4'] == 'Sucesso' and configwifi[0]['Wi-Fi 5.0'] == 'Sucesso':
        bot.send_message(mensagem.chat.id, "Configuração do Wi-Fi realizada!")
        analisedbautprov(mensagem)
        return
    elif tipoonu == 'AN5506-02-F' and configwifi[0]['Wi-Fi 2.4'] == 'Sucesso':
        bot.send_message(mensagem.chat.id, "Configuração do Wi-Fi realizada!")
        analisedbautprov(mensagem)
        return
    else:
        bot.send_message(mensagem.chat.id, "Erro na configuração do Wi-Fi, entre em contato com o setor de TI")
        print("Erro na configuração do Wi-Fi. Requisição de",informaçõesautoprovisionar[str(mensagem.chat.id)+'nomeusuario'])
        analisedbautprov(mensagem)
        return
    
# Inicio comando para Consulta Sinal
informaçõesconsultadb = {}


@bot.message_handler(commands=['ConsultarSinal'])
def consultasinal1(mensagem):
    try:
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, 
                         "Não foi identificado sobrenome em sua conta Telegram. "
                         "Por favor, acesse as configurações e adicione a informação no campo"
                         " 'Sobrenome' para continuar as interações com o Bot :)")
        return
    
    informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario'] = nomeusuario
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    if mensagem.from_user.id in autorizados:
        
        print("Requisição de "+nomeusuario+" para Consultar Sinal")
        if manutencao == True:
            bot.send_message(mensagem.chat.id, "Consulta de Sinal temporariamente suspensa. Encaminhe sua liberação para o Grupo.")
            return
        bot.send_message(mensagem.chat.id, "Informe o MAC da ONU:")

        bot.register_next_step_handler(mensagem, respostamaconuconsultasinal)

    elif mensagem.from_user.id in blacklist:
        bot.send_message(mensagem.chat.id, "Você não possui autorização para interação com este bot!")
        return
    
    else:
        bot.send_message(mensagem.chat.id, 
                         "Você não possui autorização para interação com este bot! "
                         "Digite /autorizar para iniciar sua interação")
        return    


def respostamaconuconsultasinal(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/LiberarONU' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or
          mensagem.text == '/ConsultarSinal'):
        
        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    mac_onu = mensagem.text
    if len(mac_onu) == 12 and (mac_onu[:4] == 'FHTT' or mac_onu[:4] == 'fhtt'):
        pass
    elif len(mac_onu) == 8:
        mac_onu = 'FHTT'+mac_onu
    else:
        bot.reply_to(mensagem, 'Opção inválida!')
        consultasinal1(mensagem)
        return
    informaçõesconsultadb[str(mensagem.chat.id)+'mac_onu'] = mac_onu
        
    
    bot.send_message(mensagem.chat.id, "Consultando informações...", reply_markup=types.ReplyKeyboardRemove())
    urlslotpon = f'{url_api}/obterslotpon'
    headers = {'Content-Type': 'application/json'}
    data = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "mac_onu": mac_onu
    }

    try:
        request = requests.post(urlslotpon, json=data, headers=headers)
        informacoes = json.loads(request.content)

        slot_pon = informacoes[0]['SLOT']+'-'+informacoes[0]['PON']
        informaçõesconsultadb[str(mensagem.chat.id)+'slot_pon'] = slot_pon

        ip_olt = ipsolts(informacoes[0]['OLT'])
        informaçõesconsultadb[str(mensagem.chat.id)+'ip_olt'] = ip_olt

        nomeonu = informacoes[0]['Nome ONU']
        informaçõesconsultadb[str(mensagem.chat.id)+'nomeonu'] = nomeonu

        tipoonu = informacoes[0]['Tipo ONU']
        informaçõesconsultadb[str(mensagem.chat.id)+'tipoonu'] = tipoonu

    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, "Erro na consulta de sinal. Favor tentar novamente ou entre em contato com o setor de TI.")
        return
    
    urlconsultainfo = f'{url_api}/consultainformacoes'
    datainfo = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": ip_olt,
        "mac_onu": mac_onu,
        "slot_pon": slot_pon
    }
    try:
        requestinfo = requests.post(urlconsultainfo, json=datainfo, headers=headers)
        informacoes2 = json.loads(requestinfo.content)
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, "Ocorreu um erro para consulta de informações! Tente novamente.")
        return
    try:
        db = informacoes2[0]['dB']
        modoonu = informacoes2[1]['Modo ONU']
        ipwan = informacoes2[1]['IP Wan']
    except:
        db = informacoes2[1]['dB']
        modoonu = informacoes2[0]['Modo ONU']
        ipwan = informacoes2[0]['IP Wan']
    if db != '':
        if modoonu == 'Router':
            bot.send_message(mensagem.chat.id, "\nNome ONU: "+nomeonu+"\nTipo ONU: "+
                             tipoonu+"\nModo ONU: "+modoonu+"\ndB: "+db+"\nIP WAN: "+ipwan)
        else:
            bot.send_message(mensagem.chat.id, "\nNome ONU: "+nomeonu+"\nTipo ONU: "+
                             tipoonu+"\nModo ONU: "+modoonu+"\ndB: "+db)
            
        print("Requisição para consulta de informação concluida.\nRequisitante: "+
              informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+"\nMAC: "+mac_onu+"\nOLT: "+ip_olt)
        
        bot.send_message(mensagem.chat.id, "Caso deseje refazer a consulta com o mesmo MAC, digite: /refazerconsulta")
        return  
          
    else:
        print("Requisição para consulta de informação NÃO concluida.\nRequisitante: "+
              informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+"\nMAC: "+mac_onu+"\nOLT: "+ip_olt)
        bot.send_message(mensagem.chat.id, "ONU não localizada! Por favor, verifique se "
                         "o dB informado esta correto e digite /ConsultarSinal")    
        return

@bot.message_handler(commands=['refazerconsulta'])
def refazerconsulta(mensagem):

    try:
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, 
                         "Não foi identificado sobrenome em sua conta Telegram. "
                         "Por favor, acesse as configurações e adicione a informação "
                         "no campo 'Sobrenome' para continuar as interações com o Bot :)")
        return


    informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'] = nomeusuario

    # Busca informações na biblioteca e aplica nas variáveis
    try:
        ip_olt = informaçõesconsultadb[str(mensagem.chat.id)+'ip_olt']
    except:
        bot.send_message(mensagem.chat.id, 
                         "Não consegui recuperar os dados informados anteriormente... "
                         "Por favor, refaça sua requisição acessando o comando /ConsultarSinal")
        
    mac_onu = informaçõesconsultadb[str(mensagem.chat.id)+'mac_onu']
    slot_pon = informaçõesconsultadb[str(mensagem.chat.id)+'slot_pon']
    nomeonu = informaçõesconsultadb[str(mensagem.chat.id)+'nomeonu']
    tipoonu = informaçõesconsultadb[str(mensagem.chat.id)+'tipoonu']

    bot.send_message(mensagem.chat.id, f"Consultando informações da ONU {mac_onu}...", 
                     reply_markup=types.ReplyKeyboardRemove())
    
    headers = {'Content-Type': 'application/json'}
    urlconsultainfo = f'{url_api}/consultainformacoes'
    datainfo = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": ip_olt,
        "mac_onu": mac_onu,
        "slot_pon": slot_pon
    }

    try:
        requestinfo = requests.post(urlconsultainfo, json=datainfo, headers=headers)
        informacoes2 = json.loads(requestinfo.content)
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, "Ocorreu um erro para consulta de informações! Tente novamente.")
        return
    try:
        db = informacoes2[0]['dB']
        modoonu = informacoes2[1]['Modo ONU']
        ipwan = informacoes2[1]['IP Wan']
    except:
        db = informacoes2[1]['dB']
        modoonu = informacoes2[0]['Modo ONU']
        ipwan = informacoes2[0]['IP Wan']
    if db != '':
        if modoonu == 'Router':
            bot.send_message(mensagem.chat.id, "\nNome ONU: "+nomeonu+"\nTipo ONU: "+
                             tipoonu+"\nModo ONU: "+modoonu+"\ndB: "+db+"\nIP WAN: "+ipwan)
        else:
            bot.send_message(mensagem.chat.id, "\nNome ONU: "+nomeonu+"\nTipo ONU: "+tipoonu+
                             "\nModo ONU: "+modoonu+"\ndB: "+db)
            
        print("Requisição para consulta de informação concluida.\nRequisitante: "+
              informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+"\nMAC: "+
              mac_onu+"\nOLT: "+ip_olt)
        
        bot.send_message(mensagem.chat.id, "Caso deseje refazer a consulta com os mesmo MAC, digite: /refazerconsulta")
        return        

# Fim função para consultar sinal ----------------------    

# Inicio função de liberação ---------------------------

informaçõesliberaonu = {}

@bot.message_handler(commands=['LiberarONU'])
def buscaONU(mensagem):
    try:
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, 
                         "Não foi identificado sobrenome em sua conta Telegram. "
                         "Por favor, acesse as configurações e adicione a informação no "
                         "campo 'Sobrenome' para continuar as interações com o Bot :)")
        return

    informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'] = nomeusuario

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        print("Encerrando requisição de",nomeusuario)
        return

    if mensagem.from_user.id in autorizados:
        print("Requisição de "+informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario']+" para liberação de onu")
        if manutencao == True:
            bot.send_message(mensagem.chat.id, "Liberação de ONU temporariamente suspensa. Encaminhe sua liberação para o Grupo.")
            return
        
        bot.send_message(mensagem.chat.id,"Aguarde um momento, estamos verificando as ONU's disponíveis...")
        url = f'{url_api}/buscatodasOnus'
        data = {
                "ip_servidor_tl1": iptl1,
                "porta_servidor_tl1": portatl1,
                "usuario_anm": usuariounm,
                "senha_anm": senhaunm
                }
        
        headers = {"Content-Type": "application/json"}
        request = requests.post(url, json=data, headers=headers)
        unregonus = json.loads(request.content)
        informaçõesliberaonu[str(mensagem.chat.id)+'listaonus'] = unregonus


        markupunregonus = types.ReplyKeyboardMarkup(one_time_keyboard=True)

        for objeto in unregonus:
            itembtn = types.KeyboardButton(objeto['MAC'])
            markupunregonus.add(itembtn)
        
        itembtnnone = types.KeyboardButton('Desautorizar ONU')
        markupunregonus.add(itembtnnone)
        
        
        bot.send_message(mensagem.chat.id, 
                         "Selecione a ONU que deseja liberar ou 'Desautorizar ONU' "
                         "em caso de Mudança de Endereço:", reply_markup=markupunregonus)
        bot.register_next_step_handler(mensagem, respostamaconu)

    elif mensagem.from_user.id in blacklist:
        bot.send_message(mensagem.chat.id, "Você não possui autorização para interação com este bot!")
        return
    else:
        bot.send_message(mensagem.chat.id, 
                         "Você não possui autorização para interação com este bot! "
                         "Digite /autorizar para iniciar sua interação")
        return

# Módulo substituto UTILIZAR CASO A BUSCA DE TODAS ONUS NÃO FUNCIONE
def buscaONUsub(mensagem):
    onus = oltsresposta()
    bot.send_message(mensagem.chat.id, "Selecione a OLT em que a ONU será liberada:", reply_markup=onus)

    bot.register_next_step_handler(mensagem, buscaONUsub2)
    return

# Módulo substituto
def buscaONUsub2(mensagem):
    if mensagem.from_user.id in autorizados:
        print("Requisição de "+informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario']+" para liberação de onu")
        try:
            oltip = ipsolts(mensagem.text)
        except:
            bot.send_message(mensagem.chat.id, "Nome de OLT inválido! Selecione a opção no menu abaixo")
            buscaONUsub(mensagem)
            return
        informaçõesliberaonu[str(mensagem.chat.id)+'ip'] = oltip
        bot.send_message(mensagem.chat.id,"Aguarde um momento, estamos verificando as ONU's disponíveis...",
                        reply_markup=types.ReplyKeyboardRemove())
        url = f'{url_api}/buscaOnu'
        data = {
                "ip_servidor_tl1": iptl1,
                "porta_servidor_tl1": portatl1,
                "usuario_anm": usuariounm,
                "senha_anm": senhaunm,
                "ip_olt": oltip
                }
        headers = {"Content-Type": "application/json"}
        request = requests.post(url, json=data, headers=headers)
        unregonus = json.loads(request.content)
        informaçõesliberaonu[str(mensagem.chat.id)+'listaonus'] = unregonus


        markupunregonus = types.ReplyKeyboardMarkup(one_time_keyboard=True)

        for objeto in unregonus:
            itembtn = types.KeyboardButton(objeto['MAC'])
            markupunregonus.add(itembtn)
        
        itembtnnone = types.KeyboardButton('Desautorizar ONU')
        markupunregonus.add(itembtnnone)

        bot.send_message(mensagem.chat.id, 
                         "Selecione a ONU que deseja liberar ou 'Desautorizar ONU' "
                         "em caso de Mudança de Endereço:", reply_markup=markupunregonus)
        bot.register_next_step_handler(mensagem, respostamaconu)
        return
    
    elif mensagem.from_user.id in blacklist:
        bot.send_message(mensagem.chat.id, "Você não possui autorização para interação com este bot!")
        return
    
    else:
        bot.send_message(mensagem.chat.id, 
                         "Você não possui autorização para interação com este bot! "
                         "Digite /autorizar para iniciar sua interação")
        return

def respostamaconu(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        print('Encerrando requisição de',informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'])
        return
    
    if mensagem.text == '/LiberarONU':
        print('Encerrando requisição de',informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'])
        
        bot.send_message(mensagem.chat.id, "Encerrando requisição atual e iniciando uma nova!",
                         reply_markup=types.ReplyKeyboardRemove())
        
        buscaONU(mensagem)
        return

    mac_onu = mensagem.text.upper()
    if mac_onu[:4] == 'FHTT' or mac_onu[:4] == 'fhtt':
        informaçõesliberaonu[str(mensagem.chat.id)+'mac'] = mac_onu

        for objeto in informaçõesliberaonu[str(mensagem.chat.id)+'listaonus']:
            if objeto['MAC'].upper() == mac_onu:
                informaçõesliberaonu[str(mensagem.chat.id)+'ip'] = objeto['OLTID']
                informaçõesliberaonu[str(mensagem.chat.id)+'slot'] = objeto['SLOT']
                informaçõesliberaonu[str(mensagem.chat.id)+'pon'] = objeto['PON']
                informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon'] = objeto['SLOT']+'-'+objeto['PON']
                informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] = objeto['TIPO_ONU']
    
        if informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-01-A1':

            markuptipoonu = types.ReplyKeyboardMarkup(one_time_keyboard=True,row_width=2)

            itembtn = types.KeyboardButton("ONU Mini")
            itembtn1 = types.KeyboardButton("ONU Comum 1 Porta")

            markuptipoonu.row(itembtn,itembtn1)

            bot.send_message(mensagem.chat.id, "Informe o tipo da ONU:", reply_markup=markuptipoonu)

            bot.register_next_step_handler(mensagem, obterloginpppoe)
        else:
            obterloginpppoe(mensagem)
            return
    
    elif mac_onu == 'Desautorizar ONU'.upper():
        bot.send_message(mensagem.chat.id, "Informe o MAC da ONU à ser liberada:", 
                         reply_markup=types.ReplyKeyboardRemove())

        bot.register_next_step_handler(mensagem, verificaonu)
        return
    else:
        bot.send_message(mensagem.chat.id,"Opção inválida! Digite o comando /LiberarONU para recomeçar",
                        reply_markup=types.ReplyKeyboardRemove())
        return
    

def obterloginpppoe(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or
    mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):
        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    if informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-01-A1':
        tipoonu = mensagem.text
        informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] = tipoonu

    bot.send_message(mensagem.chat.id, "Informe o login PPPoE do cliente:", 
                     reply_markup=types.ReplyKeyboardRemove())

    bot.register_next_step_handler(mensagem, obternomecliente)

def obternomecliente(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.")
        return
    
    pppoe = mensagem.text
    informaçõesliberaonu[str(mensagem.chat.id)+'pppoe'] = pppoe

    bot.send_message(mensagem.chat.id, "Informe o nome completo do cliente:")
    
    bot.register_next_step_handler(mensagem, aplicanomecliente)

def aplicanomecliente(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start' or 
        mensagem.text == '/LiberarONU'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    nomecliente = mensagem.text
    informaçõesliberaonu[str(mensagem.chat.id)+'nomecliente'] = nomecliente

    if informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'ONU Mini':
        tipoconexao = 'Bridge'
        informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'] = tipoconexao
        configuraonu(mensagem)
        return
    
    elif (informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-F' or 
          informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-04-FA'):
        
        definetipoconexao(mensagem)
        return
    
    elif (informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'ONU Comum 1 Porta' or 
          informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-B' or 
          informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-A'):
        
        tipodeconexaomarkup = types.ReplyKeyboardMarkup(one_time_keyboard=True)

        itembtnbridge = types.KeyboardButton("Bridge")
        itembtnrouter = types.KeyboardButton("Router")

        tipodeconexaomarkup.row(itembtnbridge,itembtnrouter)
        
        bot.send_message(mensagem.chat.id, "Selecione o tipo de conexão:", reply_markup=tipodeconexaomarkup)

        bot.register_next_step_handler(mensagem, definetipoconexao)

def definetipoconexao(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    if (informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-F' or 
        informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-04-FA'):
        tipoconexao = 'Router'
        informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'] = tipoconexao

    else:
        tipoconexao = mensagem.text
        informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'] = tipoconexao

    if tipoconexao == 'Router':
        bot.send_message(mensagem.chat.id, "Informe a senha PPPoE do cliente:", reply_markup=types.ReplyKeyboardRemove())

        bot.register_next_step_handler(mensagem, obtersenhapppoe)

    elif tipoconexao == 'Bridge':
        configuraonu(mensagem)
        return

def obtersenhapppoe(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    pass_pppoe = mensagem.text
    informaçõesliberaonu[str(mensagem.chat.id)+'senhacliente'] = pass_pppoe

    configuraonu(mensagem)
    return

def configuraonu(mensagem, segundatentativa=False):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    bot.send_message(mensagem.chat.id, 
                     "Um momento, estamos provisionando a ONU... Não desligue a ONU até "
                     "a finalização do processo.", reply_markup=types.ReplyKeyboardRemove())

    ip_olt = informaçõesliberaonu[str(mensagem.chat.id)+'ip']
    slot = informaçõesliberaonu[str(mensagem.chat.id)+'slot']
    pon = informaçõesliberaonu[str(mensagem.chat.id)+'pon']

    vlan = str(definevlan(ip_olt, slot, pon))
    informaçõesliberaonu[str(mensagem.chat.id)+'vlan'] = vlan

    if informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'ONU Mini':
        data = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
            "slot_pon": informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon'],
            "mac_onu": informaçõesliberaonu[str(mensagem.chat.id)+'mac'],
            "tipo_onu": informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'],
            "nome_cliente": informaçõesliberaonu[str(mensagem.chat.id)+'nomecliente'].upper(),
            "vlan": vlan,
            "tipo_conexao": informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'],
            "usuario_pppoe": informaçõesliberaonu[str(mensagem.chat.id)+'pppoe'],
            "pass_pppoe": "101010"
            }

    elif (informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'ONU Comum 1 Porta' or 
          informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-B' or 
          informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-04-FA' or 
          informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'AN5506-02-F'):
        
        if informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] == 'ONU Comum 1 Porta':
            informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'] = 'AN5506-01-A1'
        
        if informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'] == 'Router':
            data = {
                "ip_servidor_tl1": iptl1,
                "porta_servidor_tl1": portatl1,
                "usuario_anm": usuariounm,
                "senha_anm": senhaunm,
                "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
                "slot_pon": informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon'],
                "mac_onu": informaçõesliberaonu[str(mensagem.chat.id)+'mac'],
                "tipo_onu": informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'],
                "nome_cliente": informaçõesliberaonu[str(mensagem.chat.id)+'nomecliente'].upper(),
                "vlan": vlan,
                "tipo_conexao": informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'],
                "usuario_pppoe": informaçõesliberaonu[str(mensagem.chat.id)+'pppoe'],
                "pass_pppoe": informaçõesliberaonu[str(mensagem.chat.id)+'senhacliente']
                }
        elif informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'] == 'Bridge':
            data = {
                "ip_servidor_tl1": iptl1,
                "porta_servidor_tl1": portatl1,
                "usuario_anm": usuariounm,
                "senha_anm": senhaunm,
                "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
                "slot_pon": informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon'],
                "mac_onu": informaçõesliberaonu[str(mensagem.chat.id)+'mac'],
                "tipo_onu": informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu'],
                "nome_cliente": informaçõesliberaonu[str(mensagem.chat.id)+'nomecliente'].upper(),
                "vlan": vlan,
                "tipo_conexao": informaçõesliberaonu[str(mensagem.chat.id)+'tipoconexao'],
                "usuario_pppoe": informaçõesliberaonu[str(mensagem.chat.id)+'pppoe'],
                "pass_pppoe": "101010"
                }

    try:
        url = f'{url_api}/autorizaOnu'
        headers = {"Content-Type": "application/json"}
        request = requests.post(url, json=data, headers=headers)
        liberação = json.loads(request.content)

        informaçõesliberaonu[str(mensagem.chat.id)+'requestlib'] = liberação[0]['Request']
        
    except Exception as e:
        bot.send_message(mensagem.chat.id, "Ocorreu um erro para esta liberação :(")
        print(e)
        return
    tipoonu = informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu']


    if informaçõesliberaonu[str(mensagem.chat.id)+'requestlib'] == 'Sucesso':

        if tipoonu == 'AN5506-04-FA' or tipoonu == 'AN5506-02-F':
            bot.send_message(mensagem.chat.id, "Informe o Nome da Rede Wi-Fi (Máximo 32 caracteres):")
            
            bot.register_next_step_handler(mensagem, configuracaowifi)
            return
        
        bot.send_message(mensagem.chat.id, "Analisando dB da Onu...")
        analisedb(mensagem)
        return
    
    elif segundatentativa == False:
        configuraonu(mensagem,segundatentativa=True)
        return
    
    else:
        bot.send_message(mensagem.chat.id, "Ocorreu um erro para esta liberação :(")
        print(e)
        return


def analisedb(mensagem, count=0):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    vlan = informaçõesliberaonu[str(mensagem.chat.id)+'vlan']
    
    headers = {"Content-Type": "application/json"}
    urldb = f'{url_api}/consultaSinalOnu'
    datadb = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
        "slot_pon": informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon'],
        "mac_onu": informaçõesliberaonu[str(mensagem.chat.id)+'mac']
    }
    
    
    requestdb = requests.post(urldb, json=datadb, headers=headers)
    consultadb = json.loads(requestdb.content)
    
    nomeonu = informaçõesliberaonu[str(mensagem.chat.id)+'pppoe']+' - '+informaçõesliberaonu[str(mensagem.chat.id)+'nomecliente'].upper()

    if consultadb != []:
        try:
            db = consultadb[0]['SINAL'].replace(',','.')
            db = float(db)
        except:
            db = 0.0

        if db != 0.0 and db != -40.0:
            if db < -26:
                print("Requisição realizada por "+informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario']+
                      "\nNome ONU: "+nomeonu+"\nMAC: "+informaçõesliberaonu[str(mensagem.chat.id)+'mac']+
                      "\nOLT: "+informaçõesliberaonu[str(mensagem.chat.id)+'ip']+"\nSLOT-PON: "+
                      informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon']+"\nDB: "+str(db)+"\nVLAN: "+
                      vlan+"\nSTATUS: DESAUTORIZADA POR DB FORA DO PADRÃO")
                
                bot.send_message(chatidgrupodeavisos, 
                                 "Alarme! ONU com dB "+str(db)+". Nome ONU: "+informaçõesliberaonu[str(mensagem.chat.id)+
                                 'nomecliente']+" MAC: "+informaçõesliberaonu[str(mensagem.chat.id)+'mac']+". Requisição feita por "+
                                 informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'])
                
                bot.send_message(mensagem.chat.id, "Cliente com dB "+str(db)+". Desautorizando ONU...")
                desautorizaonu(mensagem)
                return
            
            else:
                print("Requisição realizada por "+informaçõesliberaonu[str(mensagem.chat.id)+
                'nomeusuario']+"\nNome ONU: "+nomeonu+"\nMAC: "+informaçõesliberaonu[str(mensagem.chat.id)+'mac']+
                "\nOLT: "+informaçõesliberaonu[str(mensagem.chat.id)+'ip']+"\nSLOT-PON: "+
                informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon']+"\nDB: "+str(db)+"\nVLAN: "+
                vlan+"\nSTATUS: "+informaçõesliberaonu[str(mensagem.chat.id)+'requestlib'])

                bot.send_message(mensagem.chat.id, "ONU com dB "+str(db)+". Configuração finalizada!")
                return
            
        elif count == 8:
            bot.send_message(chatidgrupodeavisos, 
                             "Houve erro na consulta de dB da ONU "+informaçõesliberaonu[str(mensagem.chat.id)+
                             'mac']+". Requisição feita por "+informaçõesliberaonu[str(mensagem.chat.id)+
                             'nomeusuario'])
            
            bot.send_message(mensagem.chat.id, 
                             "Liberação realizada com sucesso! Ocorreu um erro para consulta de dB"
                             ", mas estarei comunicando o setor de TI para análise.")
            
            print("Requisição realizada por "+informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario']+"\nNome ONU: "+nomeonu+"\nMAC: "+informaçõesliberaonu[str(mensagem.chat.id)+'mac']+"\nOLT: "+informaçõesliberaonu[str(mensagem.chat.id)+'ip']+"\nSLOT-PON: "+informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon']+"\nDB: "+str(db)+"\nVLAN: "+vlan+"\nSTATUS: "+informaçõesliberaonu[str(mensagem.chat.id)+'requestlib'])
            return
        
        else:
            count += 1
            time.sleep(10)
            analisedb(mensagem, count=count)
            return

    elif count == 8:
        bot.send_message(chatidgrupodeavisos, 
                         "Houve erro na consulta de dB da ONU "+informaçõesliberaonu[str(mensagem.chat.id)+
                         'mac']+". Requisição feita por "+informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'])
        
        bot.send_message(mensagem.chat.id, "Liberação realizada com sucesso! Ocorreu um erro para consulta de dB, mas estarei comunicando o setor de TI para análise.")
        return
    
    else:
        count += 1
        time.sleep(10)
        analisedb(mensagem, count=count)
        return
        
    

def configuracaowifi(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    nomewifi = mensagem.text
    informaçõesliberaonu[str(mensagem.chat.id)+'nomewifi'] = nomewifi
    bot.send_message(mensagem.chat.id, "Informe a senha do Wi-Fi (Mínimo 8 dígitos):")
    
    bot.register_next_step_handler(mensagem, configuracaowifi2)

def configuracaowifi2(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    senhawifi = mensagem.text
    tipoonu = informaçõesliberaonu[str(mensagem.chat.id)+'tipoonu']

    bot.send_message(mensagem.chat.id, "Configurando o Wi-Fi...")
    urlconfig = f'{url_api}/configuraWiFi'
    headersconfig = {"Content-Type": "application/json"}
    dataconfig = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
        "mac_onu": informaçõesliberaonu[str(mensagem.chat.id)+'mac'],
        "slot_pon": informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon'],
        "ssid_name": informaçõesliberaonu[str(mensagem.chat.id)+'nomewifi'],
        "preshared_key": senhawifi,
        "tipo_onu": tipoonu
    }

    requestconfig = requests.post(urlconfig, json=dataconfig, headers=headersconfig)
    configwifi = json.loads(requestconfig.content)

    if tipoonu == 'AN5506-04-FA' and configwifi[0]['Wi-Fi 2.4'] == 'Sucesso' and configwifi[0]['Wi-Fi 5.0'] == 'Sucesso':
        bot.send_message(mensagem.chat.id, "Configuração do Wi-Fi realizada!")
        bot.send_message(mensagem.chat.id, "Analisando dB da Onu...")
        analisedb(mensagem)
        return
    
    elif tipoonu == 'AN5506-02-F' and configwifi[0]['Wi-Fi 2.4'] == 'Sucesso':
        bot.send_message(mensagem.chat.id, "Configuração do Wi-Fi realizada!")
        bot.send_message(mensagem.chat.id, "Analisando dB da Onu...")
        analisedb(mensagem)
        return
    
    else:
        bot.send_message(mensagem.chat.id, "Erro na configuração do Wi-Fi, entre em contato com o setor de TI")

        print("Erro na configuração Wi-Fi! Requisição de:",informaçõesliberaonu[str(mensagem.chat.id)+'nomeusuario'])

        bot.send_message(mensagem.chat.id, "Analisando dB da Onu...")

        analisedb(mensagem)
        return

#Módulo para verificação e desautorização de ONU
def verificaonu(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/AlterarModoOnu' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    bot.send_message(mensagem.chat.id, "Verificando...")
    mac_onu = mensagem.text.upper()

    if len(mac_onu) == 12 and (mac_onu[:4] == 'FHTT' or mac_onu[:4] == 'fhtt'):
        mac_onu = mac_onu

    elif len(mac_onu) == 8:
        mac_onu = 'FHTT'+mac_onu

    else:
        bot.send_message(mensagem.chat.id, "MAC inválido! Verifique e informe o mac novamente")
        bot.register_next_step_handler(mensagem, verificaonu)
        return

    urlbusca = f'{url_api}/obterslotpon'
    headers = {"Content-Type": "application/json"}
    databusca = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "mac_onu": mac_onu
        }
    
    requestbusca = requests.post(urlbusca, json=databusca, headers=headers)
    buscaonu = json.loads(requestbusca.content)
    

    if buscaonu == []:
        bot.send_message(mensagem.chat.id, 
                         "A ONU não se encontra pedindo liberação. "
                         "Por favor revise os equipamentos e digite /LiberarONU para recomeçar")
        return
    
    else:
        informaçõesliberaonu[str(mensagem.chat.id)+'mac'] = mac_onu
        informaçõesliberaonu[str(mensagem.chat.id)+'ip'] = ipsolts(buscaonu[0]['OLT'])
        slot = buscaonu[0]['SLOT']
        pon = buscaonu[0]['PON']

        urldesautoriza = f'{url_api}/desautorizaOnu'
        datadesautoriza = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
            "slot_pon": slot+'-'+pon,
            "mac_onu": mac_onu
        }
        requestdesautoriza = requests.post(urldesautoriza, json=datadesautoriza, headers=headers)
        desautorizacao = json.loads(requestdesautoriza.content)
        

        if desautorizacao[0]['msg'] == 'Sucesso':
            bot.send_message(mensagem.chat.id, 
                             "ONU desautorizada no SLOT/PON: "+slot+"/"+pon+". "
                             "Por favor, aguarde a checagem e verifique se o MAC irá "
                             "aparecer na lista à seguir. Caso não apareça, reinicie o "
                             "equipamento e digite /LiberarONU")
            
            print("ONU Desautorizada por "+informaçõesliberaonu[str(mensagem.chat.id)+
            'nomeusuario']+"\nMAC: "+mac_onu+"\nSLOT-PON: "+slot+"-"+pon+
            "\nOLT: "+informaçõesliberaonu[str(mensagem.chat.id)+'ip'])

            buscaONU(mensagem)
            return
        
        else:
            bot.send_message(mensagem.chat.id, "Erro no processo de desautorização! Por favor entre em contato com o setor de TI")
            return

def desautorizaonu(mensagem):
    mac_onu = informaçõesliberaonu[str(mensagem.chat.id)+'mac']
    slot_pon = informaçõesliberaonu[str(mensagem.chat.id)+'slot_pon']

    headers = {"Content-Type": "application/json"}
    urldesautoriza = f'{url_api}/desautorizaOnu'
    datadesautoriza = {
        "ip_servidor_tl1": iptl1,
        "porta_servidor_tl1": portatl1,
        "usuario_anm": usuariounm,
        "senha_anm": senhaunm,
        "ip_olt": informaçõesliberaonu[str(mensagem.chat.id)+'ip'],
        "slot_pon": slot_pon,
        "mac_onu": mac_onu
    }

    requestdesautoriza = requests.post(urldesautoriza, json=datadesautoriza, headers=headers)
    desautorizacao = json.loads(requestdesautoriza.content)

    if desautorizacao[0]['msg'] == 'Sucesso':
        bot.send_message(mensagem.chat.id, "ONU desautorizada! Entre em contato com o setor de TI para procedência do alarme.")
        bot.send_message(chatidgrupodeavisos, "ONU desautorizada!")
        return
    else:
        bot.send_message(chatidgrupodeavisos, "Erro na desautorização da ONU. Favor realizar desconfiguração manualmente.")
        return
# Fim função de liberação ----------------------

# Inicio função de Alterar Modo ----------------

informaçõesalteramodo = {}

@bot.message_handler(commands=['AlterarModoOnu'])
def alterarmodoonu(mensagem):
    try:
        nomeusuario = mensagem.from_user.first_name+' '+mensagem.from_user.last_name
    except Exception as e:
        print(e)
        bot.send_message(mensagem.chat.id, 
                         "Não foi identificado sobrenome em sua conta Telegram. "
                         "Por favor, acesse as configurações e adicione a informação no campo "
                         "'Sobrenome' para continuar as interações com o Bot :)")
        return
    
    informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario'] = nomeusuario

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/LiberarONU' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    if mensagem.from_user.id in autorizados:
        print("Requisição de "+informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+" para Alterar Modo da ONU")
        if manutencao == True:
            bot.send_message(mensagem.chat.id, 
                             "Alteração de Modo temporariamente suspensa. "
                             "Encaminhe sua requisição para o Grupo de Liberação.")
            return
        
        bot.send_message(mensagem.chat.id, "Informe o MAC da ONU:")

        bot.register_next_step_handler(mensagem, respostaalterarmodoonu)

    elif mensagem.from_user.id in blacklist:
        bot.send_message(mensagem.chat.id, "Você não possui autorização para interação com este bot!")
        return
    
    else:
        bot.send_message(mensagem.chat.id, 
                         "Você não possui autorização para interação com este bot! "
                         "Digite /autorizar para iniciar sua interação")
        return

def respostaalterarmodoonu(mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/LiberarONU' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    mac_onu = mensagem.text.upper()
    
    if len(mac_onu) == 12 and mac_onu[:4] == 'FHTT':
        pass

    elif len(mac_onu) == 8:
        mac_onu = 'FHTT'+mac_onu

    else:
        bot.reply_to(mensagem, 'Opção inválida!')
        alterarmodoonu(mensagem)
        return
    
    informaçõesalteramodo[str(mensagem.chat.id)+'mac'] = mac_onu

    markupalteramodo = types.ReplyKeyboardMarkup(one_time_keyboard=True)

    itemrouterparabridge = types.KeyboardButton("Router para Bridge")
    itembridgepararouter = types.KeyboardButton("Bridge para Router")

    markupalteramodo.row(itemrouterparabridge, itembridgepararouter) 

    bot.send_message(mensagem.chat.id, "Selecione a alteração que deseja:", reply_markup=markupalteramodo)

    bot.register_next_step_handler(mensagem,respostaalterarmodoonu2)

def respostaalterarmodoonu2(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or
        mensagem.text == '/LiberarONU' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    alteracao = mensagem.text
    informaçõesalteramodo[str(mensagem.chat.id)+'alteracao'] = alteracao

    if alteracao == 'Bridge para Router':
        bot.send_message(mensagem.chat.id, "Informe o login PPPoE do cliente:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(mensagem, respostaalterarmodoonu3)

    else:
        respostaalterarmodoonufinal(mensagem)
        return
    
def respostaalterarmodoonu3(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or
         mensagem.text == '/LiberarONU' or mensagem.text == '/start'):
        
        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    login = mensagem.text
    informaçõesalteramodo[str(mensagem.chat.id)+'login'] = login

    bot.send_message(mensagem.chat.id, "Informe a senha PPPoE do cliente:")
    bot.register_next_step_handler(mensagem, respostaalterarmodoonu4)

def respostaalterarmodoonu4(mensagem):

    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or 
        mensagem.text == '/LiberarONU' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.")
        return
    
    senha = mensagem.text
    informaçõesalteramodo[str(mensagem.chat.id)+'senha'] = senha
    respostaalterarmodoonufinal(mensagem)
    return

def respostaalterarmodoonufinal (mensagem):
    if (mensagem.text == 'Cancelar' or mensagem.text == '/ConsultarSinal' or
        mensagem.text == '/LiberarONU' or mensagem.text == '/start'):

        bot.send_message(mensagem.chat.id, "Encerrando requisição atual.",reply_markup=types.ReplyKeyboardRemove())
        return
    
    mac_onu = informaçõesalteramodo[str(mensagem.chat.id)+'mac']
    alteracao = informaçõesalteramodo[str(mensagem.chat.id)+'alteracao']

    bot.send_message(mensagem.chat.id, "Configurando modo da ONU...")

    try:
        urlalterar = f'{url_api}/obterslotpon'
        headers = {'Content-Type': 'application/json'}
        dataalterar = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "mac_onu": mac_onu
        }

        requestalterar = requests.post(urlalterar, json=dataalterar, headers=headers)
        informacoesalterar = json.loads(requestalterar.content)
        
        slot = informacoesalterar[0]['SLOT']
        pon = informacoesalterar[0]['PON']
        slot_pon = slot+'-'+pon
        ip_olt = ipsolts(informacoesalterar[0]['OLT'])

        informaçõesalteramodo[str(mensagem.chat.id)+'ip'] = ip_olt
        informaçõesalteramodo[str(mensagem.chat.id)+'slot'] = informacoesalterar[0]['SLOT']
        informaçõesalteramodo[str(mensagem.chat.id)+'pon'] = informacoesalterar[0]['PON']

        vlan = str(definevlan(ip_olt, slot, pon))
        
        urlalterar2 = f'{url_api}/alterarmodoonu'

        if alteracao == 'Bridge para Router':
            modoantigo = 'bridge'
            dataalterar2 = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "mac_onu": mac_onu,
            "slot_pon": slot_pon,
            "ip_olt": ip_olt,
            "vlan": vlan,
            "login": informaçõesalteramodo[str(mensagem.chat.id)+'login'],
            "senha": informaçõesalteramodo[str(mensagem.chat.id)+'senha'],
            "modoantigo": modoantigo
        }

        elif alteracao == 'Router para Bridge':
            modoantigo = 'route'
            dataalterar2 = {
            "ip_servidor_tl1": iptl1,
            "porta_servidor_tl1": portatl1,
            "usuario_anm": usuariounm,
            "senha_anm": senhaunm,
            "mac_onu": mac_onu,
            "slot_pon": slot_pon,
            "ip_olt": ip_olt,
            "vlan": vlan,
            "login": 'padrao',
            "senha": '101010',
            "modoantigo": modoantigo
        }
        
        requestalterar2 = requests.post(urlalterar2, json=dataalterar2, headers=headers)
        informacoesfinal = json.loads(requestalterar2.content)
        
        if informacoesfinal[0]['mensagem'] == 'Sucesso': 

            bot.send_message(mensagem.chat.id, "Alteração concluída com sucesso!", 
                             reply_markup=types.ReplyKeyboardRemove())
            
            print("Requisição de alteração concluida.\nRequisitante: "+
                  informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+
                  "\nMAC: "+mac_onu+"\nAlteração: "+alteracao+"\nOLT: "+ip_olt)
            return
        
        else:
            print("Requisição de alteração NÃO concluida.\nRequisitante: "+
                  informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+
                  "\nMAC: "+mac_onu+"\nAlteração: "+alteracao+"\nOLT: "+ip_olt)
            
            bot.send_message(mensagem.chat.id, 
                             "Ocorreu um erro na execução de sua solicitação. "
                             "Entre em contato com o setor de TI", 
                             reply_markup=types.ReplyKeyboardRemove())
            return
        
    except Exception as e:
        print(e)
        print("Requisição de alteração NÃO concluida.\nRequisitante: "+
              informaçõesconsultadb[str(mensagem.chat.id)+'nomeusuario']+
              "\nMAC: "+mac_onu+"\nAlteração: "+alteracao+"\nOLT: "+ip_olt)
        
        bot.send_message(mensagem.chat.id, 
                         "Ocorreu um erro na execução de sua solicitação. "
                         "Entre em contato com o setor de TI", 
                         reply_markup=types.ReplyKeyboardRemove())
        return

# Fim função de Alterar Modo ---------------------------------------    



bot.infinity_polling()



