import os
import json
import time
import shutil
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

# ---------------- CONFIGURAÇÃO DE LOG ---------------- #
def configurar_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('upload_noticias_log.txt', mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# ---------------- EXTRAI APENAS A DATA (REMOVE HORÁRIO) ---------------- #
def extrair_data_sem_hora(data_completa):
    if not data_completa or data_completa == "Data não encontrada":
        return None
    data = data_completa.split()[0]
    if len(data) == 10 and data[2] == '/' and data[5] == '/':
        return data
    return None

# ---------------- SELECIONAR CATEGORIA FIXA "Geral" ---------------- #
def selecionar_categoria_geral(navegador):
    try:
        select_elem = WebDriverWait(navegador, 8).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="category_contents_id"]'))
        )
        select = Select(select_elem)
        select.select_by_visible_text("Geral")
        logging.info("Categoria 'Geral' selecionada.")
        return True
    except Exception as e:
        logging.error(f"Erro ao selecionar categoria 'Geral': {e}")
        return False

# ---------------- CADASTRAR NOTÍCIA ---------------- #
def cadastrar_noticia(navegador, noticia_path, titulo_noticia):
    try:
        with open(os.path.join(noticia_path, 'dados.json'), 'r', encoding='utf-8') as f:
            dados = json.load(f)

        titulo = dados.get('Titulo', '').strip()
        data_completa = dados.get('Data', '')
        texto = dados.get('Texto', '').strip()
        imagens = dados.get('Imagens', [])

        if not titulo:
            logging.error("Título ausente. Pulando notícia.")
            return False

        if not texto:
            texto = titulo
            logging.info("Campo 'Texto' vazio. Usando o título como conteúdo.")

        botao_cadastrar = WebDriverWait(navegador, 8).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div/div/section[2]/div/div/div/div[1]/div[1]/a'))
        )
        botao_cadastrar.click()
        logging.info("Clicando em 'Cadastrar Notícia'...")

        if not selecionar_categoria_geral(navegador):
            return False

        campo_titulo = WebDriverWait(navegador, 8).until(
            EC.presence_of_element_located((By.ID, "title"))
        )
        campo_titulo.clear()
        campo_titulo.send_keys(titulo)

        data_ddmmyyyy = extrair_data_sem_hora(data_completa)
        if data_ddmmyyyy:
            campo_data = navegador.find_element(By.ID, "publication_date")
            campo_data.clear()
            campo_data.send_keys(data_ddmmyyyy)
            logging.info(f"Data preenchida: {data_ddmmyyyy}")

        campo_texto = WebDriverWait(navegador, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.note-editable"))
        )
        campo_texto.clear()
        campo_texto.send_keys(texto)
        logging.info("Texto preenchido.")

        # === IMAGEM PRINCIPAL ===
        if imagens:
            primeira = imagens[0].strip()
            caminho_principal = os.path.join(noticia_path, primeira)
            if os.path.exists(caminho_principal):
                input_principal = navegador.find_element(By.ID, "file")
                caminho_abs = os.path.abspath(caminho_principal)
                input_principal.send_keys(caminho_abs)
                logging.info(f"Imagem principal enviada: {caminho_abs}")
            else:
                logging.warning(f"Imagem principal não encontrada: {caminho_principal}")

        # === FLUXO COM GALERIA (2+ imagens) ===
        if len(imagens) > 1:
            checkbox_galeria = navegador.find_element(By.ID, "galery")
            if not checkbox_galeria.is_selected():
                checkbox_galeria.click()
                logging.info("Galeria ativada.")

            botao_salvar = WebDriverWait(navegador, 15).until(
                EC.element_to_be_clickable((By.ID, "btn-submit"))
            )
            botao_salvar.click()
            logging.info("Clicado em 'Salvar e ir para galeria'.")

            time.sleep(5)

            caminhos_secundarios = []
            for nome in imagens[1:]:
                caminho = os.path.abspath(os.path.join(noticia_path, nome.strip()))
                if os.path.exists(caminho):
                    caminhos_secundarios.append(caminho)
                else:
                    logging.warning(f"⚠️ Imagem não encontrada: {caminho}")

            if caminhos_secundarios:
                input_galeria = WebDriverWait(navegador, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.ajax-file-upload input[type='file']"))
                )
                input_galeria.send_keys("\n".join(caminhos_secundarios))
                logging.info(f"✅ {len(caminhos_secundarios)} imagens enviadas para a galeria.")

                expected_count = len(caminhos_secundarios)

                # ✅ VALIDAÇÃO CORRIGIDA: espera que existam N option-container-box com 4 botões cada
                def todos_os_uploads_prontos(driver):
                    containers = driver.find_elements(By.CSS_SELECTOR, "div.option-container-box")
                    if len(containers) != expected_count:
                        return False
                    for c in containers:
                        botoes = c.find_elements(By.TAG_NAME, "a")
                        if len(botoes) != 4:
                            return False
                    return True

                WebDriverWait(navegador, 60).until(todos_os_uploads_prontos)
                logging.info(f"✅ Todas as {expected_count} imagens foram carregadas com sucesso na galeria.")
            else:
                logging.warning("Nenhuma imagem secundária válida para enviar.")

            botao_salvar_galeria = WebDriverWait(navegador, 15).until(
                EC.element_to_be_clickable((By.ID, "btn-submit"))
            )
            botao_salvar_galeria.click()
            logging.info("Clicado em 'Salvar' na galeria.")

        else:
            botao_salvar = WebDriverWait(navegador, 15).until(
                EC.element_to_be_clickable((By.ID, "btn-submit"))
            )
            botao_salvar.click()
            logging.info("Clicado em 'Salvar'.")

        WebDriverWait(navegador, 25).until(
            EC.url_contains("/conteudos/noticias")
        )
        logging.info("✅ Notícia cadastrada com sucesso!")
        return True

    except Exception as e:
        logging.error(f"Erro crítico ao cadastrar {noticia_path}: {e}")
        navegador.save_screenshot(f"erro_{os.path.basename(noticia_path)}.png")
        return False

# ---------------- PROCESSAR TODAS AS NOTÍCIAS ---------------- #
def processar_noticias(navegador, base_dir, sucesso_dir, erro_dir, url_lista_noticias):
    pastas = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("noticia")]
    pastas.sort(key=lambda x: int(x.replace("noticia", "")) if x.replace("noticia", "").isdigit() else 0)

    for pasta in pastas:
        caminho_pasta = os.path.join(base_dir, pasta)
        logging.info(f"\n--- Processando: {pasta} ---")

        navegador.get(url_lista_noticias)
        time.sleep(2)

        sucesso = cadastrar_noticia(navegador, caminho_pasta, pasta)
        destino = sucesso_dir if sucesso else erro_dir
        shutil.move(caminho_pasta, os.path.join(destino, pasta))
        logging.info(f"Pasta movida para: {'SUCESSO' if sucesso else 'ERRO'}")
        time.sleep(10)

# ---------------- EXECUÇÃO PRINCIPAL ---------------- #
if __name__ == "__main__":
    configurar_logging()
    logging.info("🚀 INICIANDO SCRIPT DE UPLOAD DE NOTÍCIAS")

    url_cms = "endereco"
    url_lista_noticias = "endereco/noticias/"
    usuario = "user@test.com"
    senha = "paasword"
    base_dir = "./Noticias"
    sucesso_dir = "./Noticias_Sucesso"
    erro_dir = "./Noticias_Erro"

    os.makedirs(sucesso_dir, exist_ok=True)
    os.makedirs(erro_dir, exist_ok=True)

    servico = Service(ChromeDriverManager().install())
    navegador = webdriver.Chrome(service=servico)
    navegador.maximize_window()

    try:
        navegador.get(url_cms)
        time.sleep(2)
        navegador.find_element(By.CSS_SELECTOR, 'input[type="email"][name="email"].form-control').send_keys(usuario)
        navegador.find_element(By.NAME, "password").send_keys(senha)
        navegador.find_element(By.CSS_SELECTOR, "button.btn.btn-primary.btn-block.btn-flat").click()
        logging.info("✅ Login realizado.")

        processar_noticias(navegador, base_dir, sucesso_dir, erro_dir, url_lista_noticias)

        logging.info("🎉 TODAS AS NOTÍCIAS FORAM PROCESSADAS!")

    except Exception as e:
        logging.critical(f"❗ Erro crítico no fluxo principal: {e}")
        navegador.save_screenshot("erro_critico.png")

    finally:
        navegador.quit()
        logging.info("## FIM DO SCRIPT ##")
