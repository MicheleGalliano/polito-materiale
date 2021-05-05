import os
import sys
import time
import os.path
from polito_web import PolitoWeb
from infi.systray import SysTrayIcon
from printy import printy
import win32api

configFile="config.txt"


def say_hello(systray):
    print("Buona notte!")
def writeVariables(Config):
    fpin=open(configFile,"a")
    for key in Config.keys():
        line=Config[key]
        fpin.write(line)
    fpin.close()

def checkConfig():
    Config={}
    
    project_dir=os.path.abspath(os.getcwd())# ottiene path della cartella principale del progetto
    config_file_path=os.path.join(project_dir,configFile)#crea percorso file config a partire da cartella locale
    #print(config_file_path)
    if os.path.isfile(config_file_path):
        printy("File exist","nBU")
    else:
        fpin=open(configFile,"w")
        fpin.close()
        win32api.MessageBox(0, 'controllare prompt o eseguire .bat manualmente', 'Config file non esistente,', 0x00001000 | 0x00000030 )
        printy("Config file non esistente", "yB")
        print("creo file %s in %s"%(configFile,project_dir))
        
        username=input("Inserisci username con il quale accedi sul portale: ")
        password=input("Inserisci password con la quale accedi sul portale: ")
        
        path_materiale=input("Inserisci percorso in cui si vuole salvare il materiale: ")
        
        Config["PATH_MATERIALE"] = "Percorso-Materiale," + path_materiale + "\n"
        Config["USER"]="Username,"+username+"\n"
        Config["PASS"]="Password,"+password+"\n"
        writeVariables(Config)


def getVar(variable): #variable sarebbe il nome del path a cui vuoi accedere(vedi file config)
    fpin=open(configFile,"r")
    data=fpin.read().split("\n")# legge tutto file e separa righe
    fpin.close()
    for eachLine in data:
        if eachLine!="":
            line_data=eachLine.split(",")
            Var_name=line_data[0]
            Var_path=line_data[1]
            if Var_name.strip()==variable.strip():
                return Var_path
    return ""





if __name__ == "__main__":
    menu_options = (("Buona notte", None, say_hello),) # creazione menu icona
    systray = SysTrayIcon(".\icon.ico", "Polito Materiale", menu_options)
    # creazione icona applicazione
    checkConfig()
    print()
    # Creo la sessione.
    systray.start()

    printy("PoliTo Materiale - v 1.2.0\n", "b")
    sess = PolitoWeb()

    # Imposto la cartella di download di default
    
    home = os.path.expanduser('~')
    if sys.platform.startswith('win'):
        path_materiale=getVar("Percorso-Materiale")
        sess.set_dl_folder(path_materiale)
    else:
        sess.set_dl_folder(home + "/polito-materiale")

    # Togliere il commento dalla riga seguente e modificarlo nel caso si volesse settare
    # una cartella per il download diversa da quella di default
    # sess.set_dl_folder("Path/Che/Desidero")

    # Imposto che il nome dei file sia quello che appare
    # sul sito e non quello effettivo del file. Ad esempio
    # sul sito esiste il file "Esercizio 1.pdf", quando lo si
    # scarica diventa "es_1.pdf". Scegliendo l'opzione 'web'
    # si mantiene il nome che compare sul sito, scegliendo
    # l'opzione 'nomefile' si usa il vero nome del file.
    sess.set_nome_file("web")

    # Imposto lo user agent. Si tratta di una stringa che indica che tipo
    # di browser e sistema operativo state usando, potete anche omettere questo
    # settaggio. In questo esempio si usa Safari su OSX.
    sess.set_user_agent(
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0"
    )

    # Chiedo all'utente lo username e la password.
    sess.login(username = getVar("Username"), password = getVar("Password"))
    
    var = getVar("MaterialeSelezionato")
    
    if  var == "":
        sess._get_lista_mat()

        i = 1
        printy("\nElenco del materiale disponibile - (CTRL+D per terminare)", "b>")
        for mat in sess.lista_mat:
            print("[%.2d] %s" % (i, mat[2]))
            i += 1

        n = int(input("Inserisci il numero di materie da scaricare: "))
        stringa = "MaterialeSelezionato,"
        for j in range(n):
            x = -1
            while x not in range(1, i):
                    x = input("Materia: ")
                    if x.isnumeric():
                        x = int(x)
                        sess.materieDaScaricare.append(x)
                        stringa+=str(x) + " "
                    else:
                       continue

        dizionarioMateriale = {"MaterialeSelezionato": stringa}

        writeVariables(dizionarioMateriale)
    else:
        lista = []
        for element in var.split():
            if element != "":
                lista.append(int(element))
        sess.materieDaScaricare = lista

    # Mostro il menù.
    sess.menu()
    systray.shutdown()

