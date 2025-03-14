import getpass
import html
import os
import re
import subprocess
from printy import printy

import requests


class PolitoWeb:
    dl_folder = None
    login_cookie = None
    mat_cookie = None
    lista_mat = None
    last_update_remote = None
    last_update_local = None
    MAX_RETRY = 3  # Numero massimo per i tentativi di login

    
    materieDaScaricare = []
    #materieDaScaricareText = ["Metodi matematici per l'ingegneria", "Programmazione a oggetti", "Calcolatori elettronici", "Algoritmi e programmazione"]

    nome_file = "nomefile"

    headers = {"User-Agent": "python-requests"}
    base_url = "https://didattica.polito.it/pls/portal30/"
    handler_url = base_url + "sviluppo.filemgr.handler"
    get_process_url = base_url + "sviluppo.filemgr.get_process_amount"
    file_last_update = ".last_update"  # il punto serve a nasconderlo sui sistemi UNIX

    """
        === public functions ===
    """

    def set_user_agent(self, ua):
        self.headers["User-Agent"] = ua

    def set_dl_folder(self, dl_folder):
        self._mkdir_if_not_exists(dl_folder)
        self.dl_folder = dl_folder

    def set_nome_file(self, nome):
        if nome == "web":
            self.nome_file = "name"
        elif nome == "nomefile":
            self.nome_file = "nomefile"

    def login(self, username=None, password=None):
        i = 1  # Contatore tentativi
        if username is None and password is None:
            try:
                while not self._login(username, password) and i < self.MAX_RETRY:
                    printy("Impossibile effettuare il login, riprova!", "rB")
                    i = i + 1
            except EOFError:
                print("")
                return None
        else:
            if not self._login(username, password):
                printy("Impossibile effettuare il login, riprova!", "rB")
        if i == self.MAX_RETRY:
            printy(
                "Impossibile effettuare il login dopo "
                + str(self.MAX_RETRY)
                + " tentativi.", "{r}"
            )

    def menu(self):
        while self._menu():
            self._clear()

    """
        === private functions ===
    """

    def _login(self, username, password):
        """
        :rtype: bool
        """
        if (username is None) and (password is None):
            print("Credenziali di accesso per http://didattica.polito.it")
            user = input("Username: ")
            passw = getpass.getpass("Password: ")
        else:
            user = username
            passw = password

        print("Logging in...", end="", flush=True)

        with requests.session() as s:
            s.get("https://idp.polito.it/idp/x509mixed-login", headers=self.headers)
            r = s.post(
                "https://idp.polito.it/idp/Authn/X509Mixed/UserPasswordLogin",
                data={"j_username": user, "j_password": passw},
                headers=self.headers,
            )
            rls = html.unescape(re.findall('name="RelayState".*value="(.*)"', r.text))
            if len(rls) > 0:
                relaystate = rls[0]
            else:
                return False
            samlresponse = html.unescape(
                re.findall('name="SAMLResponse".*value="(.*)"', r.text)[0]
            )
            s.post(
                "https://www.polito.it/Shibboleth.sso/SAML2/POST",
                data={"RelayState": relaystate, "SAMLResponse": samlresponse},
                headers=self.headers,
            )
            r = s.post(
                "https://login.didattica.polito.it/secure/ShibLogin.php",
                headers=self.headers,
            )
            relaystate = html.unescape(
                re.findall('name="RelayState".*value="(.*)"', r.text)[0]
            )
            samlresponse = html.unescape(
                re.findall('name="SAMLResponse".*value="(.*)"', r.text)[0]
            )
            r = s.post(
                "https://login.didattica.polito.it/Shibboleth.sso/SAML2/POST",
                data={"RelayState": relaystate, "SAMLResponse": samlresponse},
                headers=self.headers,
            )
            if (
                r.url == "https://didattica.polito.it/pls/portal30/sviluppo.pagina_studente_2016.main"
            ):  # Login Successful
                login_cookie = s.cookies
            else:
                return False
        # se sono arrivato qui vuol dire che sono loggato
        self.login_cookie = login_cookie
        return True

    def _get_lista_mat(self):
        # riceve la lista della materie sulla pagina principale del portale
        with requests.session() as s:
            s.cookies = self.login_cookie
            hp = s.get(
                "https://didattica.polito.it/portal/page/portal/home/Studente",
                headers=self.headers,
            )
            self.lista_mat = re.findall(
                "cod_ins=(.+)&incarico=([0-9]+).+>(.+)[ ]*</a>\n", hp.text
            )

    def _select_mat(self, indice):
        """
        Seleziona la materia, imposta i cookie per la materia corrente in
        self.mat_cookie,  crea la cartella per ospirate i file scaricati e
        ricava le informazioni sul last_update sia local che remote
        :param indice: indice della materia nella lista (self.lista_mat)
        """

        nome_mat = self._purge_string(self.lista_mat[indice][2])
        cartella_da_creare = os.path.join(self.dl_folder, nome_mat)
        self._mkdir_if_not_exists(cartella_da_creare)

        with requests.session() as s:
            s.cookies = self.login_cookie
            s.get(
                "https://didattica.polito.it/pls/portal30/sviluppo.chiama_materia",
                params={
                    "cod_ins": self.lista_mat[indice][0],
                    "incarico": self.lista_mat[indice][1],
                },
                headers=self.headers,
            )
            self.mat_cookie = s.cookies
            self._get_path_content(cartella_da_creare, "/")

    def _get_path_content(self, cartella, path, code="0"):
        """
        Funzione principale che si occupa ricorsivamete di scaricare i file
        :param cartella: la cartella il cui si sta lavorando (non posso usare)
                         self.working_folse perché è una funzione riscorsiva
        :param path: il persorso online
        :param code: il codice della cartella in cui mi trovo online
        """

        with requests.session() as s:
            s.cookies = self.mat_cookie
            # se non specifico il codice vuole dire che sono nella cartella iniziale e quindi
            # non devo inviare l'attributo code altrimenti mi esce un risultato non valido (??)
            if code != "0":
                json_result = s.get(
                    self.handler_url,
                    params={"action": "list", "path": path, "code": code},
                    headers=self.headers,
                )
            else:
                json_result = s.get(
                    self.handler_url,
                    params={"action": "list", "path": path},
                    headers=self.headers,
                )

            contenuto = json_result.json()

            # per controllare gli aggiornamenti mi serve il codice della cartella
            # lo prendo dal parent code del primo elemento che mi capita
            if path == "/":
                if len([i for i in contenuto["result"] if not i["name"].startswith("ZZZZZ")])==0:
                    print("\t\tNessun materiale disponibile per la materia selezionata!")
                    return
                else:
                    folder_code = contenuto["result"][0]["parent_code"]
                    self._need_to_update(cartella, folder_code)
                    self._save_update_file(cartella)

            for i in contenuto["result"]:
                if i["name"].startswith("ZZZZZ"):  # si tratta delle videolezioni
                    continue

                if i["type"] == "dir":
                    # creo la cartella su cui procedere ricorsivamente
                    name = self._purge_string(i["name"])  # pulizia dei caratteri
                    cartella_da_creare = os.path.join(cartella, name)

                    self._mkdir_if_not_exists(cartella_da_creare)
                    print("\tCartella: " + name)
                    new_path = self._my_path_join(cartella_da_creare, name)

                    # procedo ricorsivamente
                    self._get_path_content(cartella_da_creare, new_path, i["code"])

                elif i["type"] == "file":
                    if not re.search("\.([a-zA-Z]|(\d{1}(?=[a-zA-Z])))", i[self.nome_file]):   #si assume che le estensioni siano al massimo un numero e poi almeno una lettera oppure solo lettere
                        # se non trovo un'estensione uso il nome del file normale
                        try:
                            nome_del_file = i[self.nome_file]+"."+re.findall("\.([a-zA-Z]+|(\d{1}(?=[a-zA-Z])))", i["nomefile"])[0][0]  #aggiungo il punto e l'estensione al nome originale
                        except:
                            nome_del_file = i["nomefile"]   #se non c'è estensione allora uso il file originale
                        print("\t\t[", end = "")
                        printy(" WARNING  ", "o", end = "")
                        print("] Nessuna estensione trovata. Aggiungo quella originale!")
                    else:
                        nome_del_file = i[self.nome_file]

                    if self._need_to_update_this(cartella, nome_del_file, i["date"]):
                        # scarico il file
                        print("\t\t[ DOWNLOAD ] " + nome_del_file)
                        self._download_file(cartella, nome_del_file, path, i["code"])
                    else:
                        print("\t\t[    OK    ] " + nome_del_file)

    def _download_file(self, cartella, name, path, code):
        with requests.session() as s:
            s.cookies = self.mat_cookie
            file = s.get(
                self.handler_url,
                params={
                    "action": "download",
                    "path": (path + "/" + name),
                    "code": code,
                },
                allow_redirects=True,
                headers=self.headers,
            )
            if (
                "text/html" in file.headers["content-type"]
                and '<body onload="document.forms[0].submit()">' in file.text
            ):
                file = s.post(
                    "https://file.didattica.polito.it/Shibboleth.sso/SAML2/POST",
                    data={
                        "RelayState": html.unescape(
                            re.findall('name="RelayState".*value="(.*)"', file.text)[0]
                        ),
                        "SAMLResponse": html.unescape(
                            re.findall('name="SAMLResponse".*value="(.*)"', file.text)[
                                0
                            ]
                        ),
                    },
                    allow_redirects=True,
                    headers=self.headers,
                )
            try:
                name = self._purge_string(name)
                open(os.path.join(cartella, name), "wb").write(file.content)
            except ValueError:
                # nel caso in cui non si riuscisse a salvere il file
                # si pulisce meglio il nome
                name = self._purge_string(name, "strong")
                open(os.path.join(cartella, name), "wb").write(file.content)

    def _menu(self):
        # se non ho ancora salvato la lista delle materie per questa sessione
        # la salvo il self.lista_mat
        if self.lista_mat is None:
            self._get_lista_mat()

        i = 1
        print("\n")
        for mat in self.lista_mat:
            print("[%.2d] %s" % (i, mat[2]))
            if i in self.materieDaScaricare:
                self._select_mat(i - 1)
            i += 1
        print("--- Fine! ---")
        return False

    def _last_update_remote(self, folder_code):
        """
        imposta self.last_update_remote
        :param folder_code: codice della cartella online
        """
        with requests.session() as s:
            s.cookies = self.mat_cookie
            json_result = s.get(self.get_process_url, params={"items": folder_code})
            if json_result:
                json_result = json_result.json()
                self.last_update_remote = json_result["result"]["lastUpload"]
            else:
                print("Impossibile stabilire la data dell'ultimo aggiornamento")
                self.last_update_remote = None

    def _last_update_local(self, cartella):
        """
        imposta self.last_update_local
        :param cartella: la cartella in cui sto lavorando
        """

        file_da_controllare_nt = os.path.join(
            *[self.dl_folder, cartella, self.file_last_update]
        )

        if os.path.isfile(file_da_controllare_nt):
            with open(file_da_controllare_nt, "r") as f:
                self.last_update_local = f.read()
        else:
            self.last_update_local = None

    def _need_to_update(self, cartella, folder_code):
        self._last_update_local(cartella)
        self._last_update_remote(folder_code)
        if self.last_update_local is not None and self.last_update_remote is not None:
            if self.last_update_local < self.last_update_remote:
                return True
            else:
                return False
        else:
            return True  # se non trovo niente è come se dovessi aggiornare tutto

    def _save_update_file(self, cartella):
        """
        salva il file per tenere traccia dell'ultimo aggiornamento
        :return:
        """

        # se il file esiste già bisogna usa 'r+' e non 'w' per motivi
        # di windows di operazioni su file nascosti
        update_file = os.path.join(*[self.dl_folder, cartella, self.file_last_update])

        mode = "r+" if os.path.isfile(update_file) else "w"

        with open(update_file, mode) as f:
            f.write(self.last_update_remote)

        # nascondo il file se sono su windows se l'ho creato per la prima volta (modo 'w')
        if os.name == "nt" and mode == "w":
            self._hide_file_in_win32(update_file)

    def _need_to_update_this(self, cartella, nomefile, data):
        """
        Restituiisce vero nel caso in cui il file è più aggiornato
        rispetto alla versione locale o in caso il file non
        ci sia prorpio nella versione locale. Per la versione locale
        controlla sia con _purge_string che con _purge_string_strong
        :param data: la data del file che sto considerando
        :return: bool
        """

        nomefile = self._purge_string(nomefile)
        file_da_controllare = os.path.join(*[self.dl_folder, cartella, nomefile])

        if not os.path.isfile(file_da_controllare):
            nomefile = self._purge_string(nomefile, "strong")
            file_da_controllare = os.path.join(*[self.dl_folder, cartella, nomefile])
            if not os.path.isfile(file_da_controllare):
                return True

        if self.last_update_local is None:
            return True

        if self.last_update_local < data:
            return True

        return False

    """
        === static methods ===
    """

    @staticmethod
    def _my_path_join(a, b):
        if a.endswith("/"):
            return a + b
        else:
            return a + "/" + b

    def _purge_string(self, a, strong=None):
        if strong is None:
            return re.sub('[/:*?"<>|]', "", a).strip()
        elif strong == "strong":
            # se è presente l'attributo strong faccio il purge_string
            # leggero e poi quello strong
            return re.sub("[^a-zA-Z0-9 .]", "", self._purge_string(a)).strip()
        else:
            return a

    @staticmethod
    def _mkdir_if_not_exists(folder):
        if not os.path.isdir(folder):
            os.mkdir(folder)

    @staticmethod
    def _clear():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def _hide_file_in_win32(file_da_nascondere):
        """
        Funzione che permette di nascondere un file su windows
        in particolare quello del last_update
        :param file_da_nascondere: path del file na nascondere
        """
        try:
            subprocess.call(["attrib", "+H", file_da_nascondere])
        except ValueError:
            print("[  ERRORE  ] Impossibile nascondere il file di timestamp")
