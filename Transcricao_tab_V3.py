import os
import sys
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPlainTextEdit, QComboBox, QMessageBox, QProgressBar,
    QListWidget, QLineEdit, QPushButton, QToolButton, QMenu
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QTextCursor, QIcon, QAction

from platform_utils import is_windows, is_linux
# Importação segura do módulo de logs
try:
    from logs_tab import adicionar_log
except ImportError:
    def adicionar_log(mensagem):
        print(f"LOG: {mensagem}")


def get_app_dir():
    """Retorna o diretório do app, considerando empacotamento."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "ProcessadorDeAudioVideo")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return app_dir


# Caminhos globais
PASTA_SCRIPT = get_app_dir()
HISTORICO_PATH = os.path.join(PASTA_SCRIPT, "historico.json")
CONFIG_PATH = os.path.join(PASTA_SCRIPT, "config.json")
TRANSCRICOES_DIR = os.path.join(PASTA_SCRIPT, "Transcricoes")

# Criar pasta de transcrições se não existir
if not os.path.exists(TRANSCRICOES_DIR):
    os.makedirs(TRANSCRICOES_DIR, exist_ok=True)

# Idiomas suportados
IDIOMAS = [
    ("auto", "Detectar automático"),
    ("pt", "Português"),
    ("en", "Inglês"),
    ("es", "Espanhol"),
    ("fr", "Francês"),
    ("de", "Alemão"),
]


def carregar_config():
    """Carrega configuração do JSON."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def salvar_config(config):
    """Salva configuração no JSON."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

FORCE_CORE_SUBPROCESS = True


class TranscricaoTextEdit(QTextEdit):
    """Campo de texto personalizado com suporte a arrastar e soltar e botão de fonte."""
    fileDropped = pyqtSignal(str)
    fonteAlterada = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(True)
        self._tamanho_fonte = 14
        self.setProperty("tamanhoFonte", self._tamanho_fonte)
        self.setObjectName("TranscricaoTextEdit")
        self._apply_custom_style(self._tamanho_fonte)
        self._font_button = None
        self._create_font_size_button()
        self._setup_placeholder()

    def _setup_placeholder(self):
        """Texto inicial quando não há conteúdo."""
        self.setHtml("""
            <div style="text-align:center;margin-top:52px;">
                <span style="font-size:17px;font-weight:600;">
                    Arraste e solte um arquivo de áudio ou vídeo aqui
                </span><br>
                <span style="font-size:13px;">
                    ou veja aqui o texto transcrito.
                </span>
            </div>
        """)

    def _apply_custom_style(self, tamanho):
        """Aplica estilo com tamanho de fonte dinâmico."""
        self.setStyleSheet(f"""
            QTextEdit#TranscricaoTextEdit {{
                font-size: {tamanho}px;
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 18px;
            }}
        """)

    def setFontSize(self, tamanho):
        """Altera o tamanho da fonte."""
        self._tamanho_fonte = tamanho
        self.setProperty("tamanhoFonte", tamanho)
        self._apply_custom_style(tamanho)
        self.fonteAlterada.emit(tamanho)

    def _create_font_size_button(self):
        """Botão para alterar tamanho da fonte."""
        self._font_button = QToolButton(self)
        self._font_button.setIcon(QIcon.fromTheme("format-font-size"))
        self._font_button.setText("Aa")
        self._font_button.setToolTip("Alterar tamanho da fonte da transcrição")
        self._font_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._font_button.setStyleSheet("""
            QToolButton {
                background: transparent;
                color: #b3bab7;
                font-size: 13px;
                padding: 2px 8px 2px 6px;
                border: none;
            }
            QToolButton:hover {
                color: #8fffa0;
            }
        """)
        font_menu = QMenu(self)
        for size in [12, 14, 16, 18, 20, 24]:
            act = QAction(f"{size}px", self)
            act.setData(size)
            act.triggered.connect(lambda checked, s=size: self.setFontSize(s))
            font_menu.addAction(act)
        self._font_button.setMenu(font_menu)
        self._font_button.setFixedSize(30, 22)
        self._font_button.raise_()
        self._font_button.show()

    def resizeEvent(self, event):
        """Atualiza posição do botão de fonte ao redimensionar."""
        super().resizeEvent(event)
        if self._font_button:
            m_top = 7
            m_right = 40
            btn_w, btn_h = self._font_button.width(), self._font_button.height()
            self._font_button.move(self.width() - btn_w - m_right, m_top)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.mp3', '.mp4', '.wav', '.m4a', '.ogg', '.flac')):
                    self.fileDropped.emit(file_path)
                    break
        event.acceptProposedAction()

class TranscricaoThread(QThread):
    progresso = pyqtSignal(int, str, str)
    resultado = pyqtSignal(str)
    erro = pyqtSignal(str)
    cancelado = pyqtSignal()
    finished = pyqtSignal()
    log = pyqtSignal(str)

    def __init__(self, caminho, modelo, idioma, log_callback=None):
        super().__init__()
        self.caminho = caminho
        self.modelo = modelo
        self.idioma = idioma
        self._cancelado = False
        self.log_callback = log_callback
        self._proc = None  # Popen do core

    def _log(self, msg):
        self.log.emit(msg)
        if self.log_callback:
            self.log_callback(msg)

    def cancel(self):
        self._cancelado = True
        # Mata o processo se estiver rodando
        if self._proc and self._proc.poll() is None:
            try:
                self._log("[CORE] Cancelando subprocesso...")
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        try:
            # Chama primeiro o core (subprocesso)
            self.progresso.emit(5, "Preparando", "Preparando subprocesso")
            core_result = self._executar_core_subprocesso()
            if self._cancelado:
                self.cancelado.emit()
                return

            if not core_result.get("success"):
                self._log(f"[CORE] Falhou: {core_result.get('error')}")
                # Fallback
                self._log("[FALLBACK] Tentando fallback (whisper_simple)")
                fallback = self._executar_fallback()
                if fallback.get("success"):
                    self.resultado.emit(fallback["text"])
                else:
                    self.erro.emit(fallback.get("error", "Erro desconhecido"))
            else:
                self.resultado.emit(core_result["text"])
        except Exception as e:
            import traceback
            self._log(traceback.format_exc())
            self.erro.emit(str(e))
        finally:
            self.finished.emit()

    def _executar_core_subprocesso(self):
        import subprocess, json, os, sys, time
        try:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core_subprocess.py")
            if not os.path.exists(script_path):
                return {"success": False, "error": "core_subprocess.py não encontrado"}

            cmd = [sys.executable, script_path, self.caminho, self.modelo, self.idioma or "auto"]
            self._log(f"[CORE] Executando: {cmd}")

            # Windows: esconder janela
            startupinfo = None
            creationflags = 0
            if sys.platform.startswith("win"):
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags = subprocess.CREATE_NO_WINDOW
                except Exception:
                    pass

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                startupinfo=startupinfo
            )

            # Leitura incremental (pode evoluir para progresso)
            stdout_lines = []
            last_emit = 10
            while True:
                if self._cancelado:
                    self.cancel()
                    return {"success": False, "error": "Cancelado pelo usuário"}
                line = self._proc.stdout.readline()
                if not line:
                    if self._proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue
                stdout_lines.append(line)

                # Emite algum progresso “falso” para animar (pode ser refinado)
                if last_emit < 90:
                    last_emit += 5
                    self.progresso.emit(last_emit, "Processando", "Diarizando / Transcrevendo")

            rc = self._proc.poll()
            stderr_all = self._proc.stderr.read() if self._proc.stderr else ""
            if rc != 0:
                return {"success": False, "error": stderr_all.strip() or f"Retorno {rc}"}

            # Pegar última linha JSON
            json_obj = None
            for ln in reversed(stdout_lines):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    json_obj = json.loads(ln)
                    break
                except Exception:
                    continue
            if not json_obj:
                return {"success": False, "error": "Saída do core sem JSON válido"}

            self.progresso.emit(100, "Concluído", "Finalizado")
            self._log("[CORE] Pipeline finalizado com sucesso (subprocesso)")
            return json_obj
        except Exception as e:
            return {"success": False, "error": f"Exceção core: {e}"}

    def _executar_fallback(self):
        # Reuso do whisper_simple existente
        try:
            import os, sys, traceback
            self._log("[FALLBACK] Iniciando")
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_simple.py"), "r", encoding="utf-8") as f:
                code = f.read()
            ns = {"__file__": "whisper_simple.py", "os": os, "sys": sys, "traceback": traceback}
            exec(code, ns)
            fn = ns.get("transcrever_audio")
            if not fn:
                return {"success": False, "error": "Função transcrever_audio não encontrada no fallback"}
            res = fn(self.caminho, self.modelo, self.idioma)
            return res
        except Exception as e:
            return {"success": False, "error": f"Fallback falhou: {e}"}


class AnimatedProgressBar(QProgressBar):
    """Barra de progresso com animação suave."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._indeterminate = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def setIndeterminate(self, on=True):
        self._indeterminate = on
        if on:
            self.setRange(0, 0)
            self.timer.start(50)
        else:
            self.setRange(0, 100)
        self.timer.stop()

    def _tick(self):
        self.setFormat("Processando...")

    def setFormatWithStatus(self, status, percent=None):
        if percent is not None:
            self.setFormat(f"{status}  {percent}%")
        else:
            self.setFormat(f"{status}")


class TranscricaoTab(QWidget):
    """Aba principal de transcrição de áudio."""

    _whisper_loaded = False
    _import_error = None

    def __init__(self):
        super().__init__()
        self.config = carregar_config()
        self.caminho_arquivo = ""
        self.thread = None
        self._historico_cache = []
        self.setup_ui()
        QTimer.singleShot(1000, self.carregar_whisper_tardio)

    def setup_ui(self):
        # Layout principal
        layout_principal = QHBoxLayout()
        layout_esquerda = QVBoxLayout()
        layout_direita = QVBoxLayout()

        # Linha superior: seletores
        hlayout_top = QHBoxLayout()
        self.combo_modelos = QComboBox()
        self.combo_modelos.addItems(["tiny", "base", "small", "medium", "large"])
        self.combo_idioma = QComboBox()
        for cod, nome in IDIOMAS:
            self.combo_idioma.addItem(nome, cod)
        self.btn_abrir = QPushButton("Selecionar arquivo")
        self.btn_abrir.setMinimumWidth(140)
        self.btn_abrir.clicked.connect(self.selecionar_arquivo)

        hlayout_top.addWidget(QLabel("Modelo Whisper:"))
        hlayout_top.addWidget(self.combo_modelos)
        hlayout_top.addSpacing(12)
        hlayout_top.addWidget(QLabel("Idioma:"))
        hlayout_top.addWidget(self.combo_idioma)
        hlayout_top.addStretch(1)
        hlayout_top.addWidget(self.btn_abrir)
        layout_esquerda.addLayout(hlayout_top)

        # Label do arquivo
        self.label_arquivo = QLabel("Arquivo: nenhum selecionado")
        self.label_arquivo.setObjectName("ArquivoLabel")
        layout_esquerda.addWidget(self.label_arquivo)

        # Botões de transcrição
        botoes_transcricao_layout = QHBoxLayout()
        self.btn_transcrever = QPushButton("Transcrever")
        self.btn_transcrever.clicked.connect(self.transcrever)
        self.btn_cancelar = QPushButton("Cancelar Transcrição")
        self.btn_cancelar.clicked.connect(self.cancelar_transcricao)
        self.btn_cancelar.setEnabled(False)
        botoes_transcricao_layout.addWidget(self.btn_transcrever)
        botoes_transcricao_layout.addWidget(self.btn_cancelar)
        layout_esquerda.addLayout(botoes_transcricao_layout)

        # Progresso
        self.label_progresso = QLabel("Progresso:")
        self.label_progresso.setVisible(False)
        self.label_etapa = QLabel("")
        self.label_etapa.setVisible(False)
        hlayout_progresso = QHBoxLayout()
        hlayout_progresso.addWidget(self.label_progresso)
        hlayout_progresso.addStretch(1)
        hlayout_progresso.addWidget(self.label_etapa)
        layout_esquerda.addLayout(hlayout_progresso)

        self.progress = AnimatedProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.smooth_progress_timer = QTimer()
        self.smooth_progress_timer.timeout.connect(self._incrementar_progresso_suave)
        self.smooth_target = 0
        self.smooth_status = ""
        layout_esquerda.addWidget(self.progress)

        # Área de transcrição
        tamanho_fonte = self.config.get("tamanho_fonte_transcricao", 14)
        self.texto_transcricao = TranscricaoTextEdit()
        self.texto_transcricao.setObjectName("TranscricaoTextEdit")
        self.texto_transcricao.setFontSize(tamanho_fonte)
        self.texto_transcricao.fileDropped.connect(self.arquivo_arrastado)
        layout_esquerda.addWidget(self.texto_transcricao)

        # Botões de download
        btns_download_layout = QHBoxLayout()
        self.btn_download_transcricao = QPushButton("Baixar Transcrição")
        self.btn_download_transcricao.clicked.connect(self.baixar_transcricao)
        btns_download_layout.addWidget(self.btn_download_transcricao)
        self.btn_download_traducao = QPushButton("Baixar Tradução (EN)")
        self.btn_download_traducao.clicked.connect(self.baixar_traducao)
        self.btn_download_traducao.setEnabled(False)
        btns_download_layout.addWidget(self.btn_download_traducao)
        btn_limpar_memoria = QPushButton("Limpar Memória")
        btn_limpar_memoria.clicked.connect(self.limpar_memoria)
        btns_download_layout.addWidget(btn_limpar_memoria)
        layout_esquerda.addLayout(btns_download_layout)

        # Histórico
        self.busca_historico = QLineEdit()
        self.busca_historico.setPlaceholderText("Buscar no histórico...")
        self.busca_historico.textChanged.connect(self.filtrar_historico)
        layout_direita.addWidget(self.busca_historico)
        layout_direita.addWidget(QLabel("Histórico de transcrições:"))
        self.lista_historico = QListWidget()
        self.lista_historico.itemClicked.connect(self.abrir_do_historico)
        layout_direita.addWidget(self.lista_historico)

        # Botões do histórico
        botoes_historico_layout = QVBoxLayout()
        self.btn_remover = QPushButton("Remover selecionado")
        self.btn_limpar = QPushButton("Limpar histórico")
        self.btn_remover.clicked.connect(self.remover_selecionado)
        self.btn_limpar.clicked.connect(self.limpar_historico)
        botoes_historico_layout.addWidget(self.btn_remover)
        botoes_historico_layout.addWidget(self.btn_limpar)
        layout_direita.addLayout(botoes_historico_layout)

        # Console
        layout_direita.addWidget(QLabel("Console:"))
        self.console_log = QPlainTextEdit()
        self.console_log.setObjectName("ConsoleLog")
        self.console_log.setReadOnly(True)
        self.console_log.setMaximumBlockCount(300)
        layout_direita.addWidget(self.console_log)

        layout_direita.setStretch(2, 4)
        layout_direita.setStretch(5, 6)

        # Monta layout
        layout_principal.addLayout(layout_esquerda, 5)
        layout_principal.addLayout(layout_direita, 2)
        self.setLayout(layout_principal)

        # Inicializa
        self.thread = None
        self.carregar_historico()
        self.atualizar_config_interface()
        self.adicionar_log_console("Programa iniciado.")
        self.log_criacao_pastas_arquivos()

    def carregar_whisper_tardio(self):
        """
        Valida whisper de forma silenciosa. No Windows, se falhar,
        continuamos porque usamos subprocesso (core_subprocess).
        """
        try:
            from whisper_import import import_whisper_safely
            whisper, error = import_whisper_safely()
            if error:
                self._whisper_loaded = False
                self._import_error = error
                self.adicionar_log_console(f"Whisper local não carregado (OK para subprocesso): {error}")
            else:
                self._whisper_loaded = True
                self._import_error = None
                self.adicionar_log_console("Whisper local validado.")
        except Exception as e:
            self._whisper_loaded = False
            self._import_error = str(e)
            self.adicionar_log_console(f"Falha ao inicializar Whisper (ignorando para subprocesso): {e}")

    def uses_core_subprocess(self):
        """
        Retorna True se pudermos usar o core em subprocesso (arquivo presente),
        mesmo que o whisper local não tenha carregado.
        """
        try:
            core_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core_subprocess.py")
            return os.path.exists(core_path)
        except Exception:
            return False

    def verificar_whisper_carregado(self):
        """
        Regras:
          - Se whisper local carregou: OK.
          - Caso contrário, se existe core_subprocess.py ou FORCE_CORE_SUBPROCESS: OK.
          - Caso contrário, bloquear.
        """
        if self._whisper_loaded:
            return True

        if FORCE_CORE_SUBPROCESS or self.uses_core_subprocess():
            self.adicionar_log_console("Prosseguindo com core em subprocesso sem whisper local.")
            return True

        # Bloqueia somente se realmente não houver alternativa
        if self._import_error:
            QMessageBox.critical(self, "Erro", f"Whisper não disponível: {self._import_error}")
        else:
            QMessageBox.critical(self, "Aguarde", "Bibliotecas ainda não disponíveis.")
        return False

    def transcrever(self):
        """
        Inicia o processo de transcrição. Removida checagem direta de _whisper_loaded.
        """
        if not self.caminho_arquivo:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo primeiro.")
            return

        # Usa a lógica unificada (agora permite fallback subprocesso core)
        if not self.verificar_whisper_carregado():
            return

        if not os.path.exists(self.caminho_arquivo):
            QMessageBox.warning(self, "Erro", f"Arquivo não encontrado: {self.caminho_arquivo}")
            return

        # Garantir que não há thread anterior
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            try:
                self.thread.quit()
                self.thread.wait(1200)
            except Exception:
                pass
            self.thread = None

        modelo = self.combo_modelos.currentText()
        idioma = self.combo_idioma.currentData()

        self.texto_transcricao.setHtml(
            "<div style='color:#b0f7b8;font-size:17px;text-align:center;'>Processando, aguarde...</div>"
        )
        self.label_progresso.setVisible(True)
        self.progress.setVisible(True)
        self.label_etapa.setVisible(True)
        self.progress.setIndeterminate(True)
        self.progress.setFormatWithStatus("Preparando", None)
        self.smooth_target = 0
        self.smooth_status = "Preparando"
        self.smooth_progress_timer.start(40)

        self.thread = TranscricaoThread(
            self.caminho_arquivo, modelo, idioma,
            log_callback=self.adicionar_log_console
        )
        self.thread.progresso.connect(self.atualizar_progresso_detalhado)
        self.thread.resultado.connect(self.exibir_transcricao)
        self.thread.erro.connect(self.exibir_erro)
        self.thread.cancelado.connect(self.tratamento_cancelado)
        self.thread.log.connect(self.adicionar_log_console)
        self.thread.finished.connect(self.limpar_thread)

        self.btn_cancelar.setEnabled(True)
        self.thread.start()

    def closeEvent(self, event):
        """Encerra thread ao fechar."""
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread.quit()
            self.thread.wait()
        event.accept()

    def adicionar_log_console(self, mensagem):
        self.console_log.appendPlainText(mensagem)
        self.console_log.moveCursor(QTextCursor.MoveOperation.End)
        adicionar_log(mensagem)

    def log_criacao_pastas_arquivos(self):
        created = []
        for pasta in ["Transcricoes", "saida_audio"]:
            path = os.path.join(PASTA_SCRIPT, pasta)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                created.append(pasta)
        for arq in ["config.json", "historico.json"]:
            path = os.path.join(PASTA_SCRIPT, arq)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("[]" if arq == "historico.json" else "{}")
                created.append(arq)
        if created:
            self.adicionar_log_console(f"Criados: {', '.join(created)}")
        else:
            self.adicionar_log_console("Pastas e arquivos necessários já existem.")

    def carregar_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def atualizar_config_interface(self):
        self.config = self.carregar_config()
        modelo_salvo = self.config.get("modelo", "small")
        idx_modelo = self.combo_modelos.findText(modelo_salvo)
        if idx_modelo >= 0:
            self.combo_modelos.setCurrentIndex(idx_modelo)
        else:
            self.combo_modelos.setCurrentIndex(2)
        config_idioma = self.config.get("idioma", "auto")
        idx_idioma = 0
        for i, (cod, nome) in enumerate(IDIOMAS):
            if cod == config_idioma:
                idx_idioma = i
                break
        self.combo_idioma.setCurrentIndex(idx_idioma)

    def selecionar_arquivo(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Selecione um arquivo de áudio ou vídeo",
            "", "Áudio/Vídeo (*.mp3 *.mp4 *.wav *.m4a *.ogg *.flac)"
        )
        if fname:
            self.setar_arquivo(fname)

    def arquivo_arrastado(self, file_path):
        self.setar_arquivo(file_path)

    def setar_arquivo(self, caminho):
        try:
            tamanho_bytes = os.path.getsize(caminho)
            tamanho_mb = tamanho_bytes / (1024 * 1024)
        except Exception:
            tamanho_mb = 0
        aviso_mb = self.config.get("aviso_tamanho_mb", 300)
        if tamanho_mb > aviso_mb:
            resposta = QMessageBox.question(
                self,
                "Aviso: Arquivo grande",
                f"O arquivo selecionado possui mais de {aviso_mb} MB ({tamanho_mb:.1f} MB).\n"
                f"A transcrição pode demorar bastante tempo, dependendo do seu computador.\n\nDeseja continuar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if resposta != QMessageBox.StandardButton.Yes:
                self.adicionar_log_console(f"Seleção de arquivo cancelada pelo usuário (tamanho: {tamanho_mb:.1f} MB).")
                return
        self.caminho_arquivo = caminho
        nome = os.path.basename(caminho)
        tamanho_str = f" ({tamanho_mb:.1f} MB)" if tamanho_mb else ""
        self.label_arquivo.setText(f'📎 Arquivo: {nome}{tamanho_str}')
        self.adicionar_log_console(f"Arquivo selecionado: {nome}{tamanho_str}")

    def transcrever(self):
        if not self.caminho_arquivo:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo primeiro.")
            return

        if not self.verificar_whisper_carregado():
            return
    
        if not os.path.exists(self.caminho_arquivo):
            QMessageBox.warning(self, "Erro", f"Arquivo não encontrado: {self.caminho_arquivo}")
            return
    
        # Garantir que não há thread anterior rodando
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(1000)
            self.thread = None

        modelo = self.combo_modelos.currentText()
        idioma = self.combo_idioma.currentData()
    
        self.texto_transcricao.setHtml("<div style='color:#b0f7b8;font-size:17px;text-align:center;'>Processando, aguarde...</div>")
        self.label_progresso.setVisible(True)
        self.progress.setVisible(True)
        self.label_etapa.setVisible(True)
        self.progress.setIndeterminate(True)
        self.progress.setFormatWithStatus("Preparando", None)
        self.smooth_target = 0
        self.smooth_status = "Preparando"
        self.smooth_progress_timer.start(40)
    
        self.thread = TranscricaoThread(
            self.caminho_arquivo, modelo, idioma,
            log_callback=self.adicionar_log_console
        )
        self.thread.progresso.connect(self.atualizar_progresso_detalhado)
        self.thread.resultado.connect(self.exibir_transcricao)
        self.thread.erro.connect(self.exibir_erro)
        self.thread.cancelado.connect(self.tratamento_cancelado)
        self.thread.log.connect(self.adicionar_log_console)
        self.thread.finished.connect(self.limpar_thread)
    
        self.btn_cancelar.setEnabled(True)
        self.thread.start()

    def atualizar_progresso_detalhado(self, valor, texto, etapa):
        if etapa:
            self.label_etapa.setText(etapa)
            self.smooth_status = etapa
        else:
            self.label_etapa.setText("Processando...")
            self.smooth_status = "Processando..."
        if valor is None or valor < 0:
            self.progress.setIndeterminate(True)
            self.progress.setFormatWithStatus(self.smooth_status)
        else:
            self.progress.setIndeterminate(False)
            self.smooth_target = valor
            self.progress.setFormatWithStatus(self.smooth_status, valor)
        if texto:
            self.adicionar_log_console(f"{texto}")

    def _incrementar_progresso_suave(self):
        atual = self.progress.value()
        if self.progress._indeterminate:
            return
        if atual < self.smooth_target:
            self.progress.setValue(atual + 1)
            self.progress.setFormatWithStatus(self.smooth_status, atual + 1)
        elif atual > self.smooth_target:
            self.progress.setValue(self.smooth_target)
            self.progress.setFormatWithStatus(self.smooth_status, self.smooth_target)
        if self.progress.value() >= 100:
            self.smooth_progress_timer.stop()

    def cancelar_transcricao(self):
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread.wait(1500)
        self.btn_cancelar.setEnabled(False)
        self.progress.setVisible(False)
        self.label_progresso.setVisible(False)
        self.label_etapa.setVisible(False)
        self.progress.setIndeterminate(False)
        self.smooth_progress_timer.stop()
        self.texto_transcricao.setHtml("""
            <div style="color:#ff6b6b;font-size:16px;text-align:center;font-weight:bold;padding:10px 0;">
                Transcrição cancelada pelo usuário.
            </div>
        """)
        self.adicionar_log_console("Transcrição cancelada pelo usuário.")

    def limpar_thread(self):
        """Limpa a referência da thread após finalização"""
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
        self.btn_cancelar.setEnabled(False)

    def limpar_memoria(self):
        """Limpeza manual de memória"""
        try: 
            import gc
            gc.collect()
            self.adicionar_log_console("Memória limpa manualmente.")
            QMessageBox.information(self, "Sucesso", "Memória limpa com sucesso.")
        except Exception as e:
            self.adicionar_log_console(f"Erro ao limpar memória: {e}")

    def tratamento_cancelado(self):
        self.progress.setVisible(False)
        self.label_progresso.setVisible(False)
        self.label_etapa.setVisible(False)
        self.btn_cancelar.setEnabled(False)
        self.progress.setIndeterminate(False)
        self.smooth_progress_timer.stop()
        self.texto_transcricao.setHtml("""
            <div style="color:#ff6b6b;font-size:16px;text-align:center;font-weight:bold;padding:10px 0;">
                Transcrição cancelada pelo usuário.
            </div>
        """)
        self.adicionar_log_console("Transcrição cancelada pelo usuário.")

    def exibir_transcricao(self, texto):
        self.texto_transcricao.setPlainText(texto)
        self.progress.setValue(100)
        self.progress.setVisible(False)
        self.label_progresso.setVisible(False)
        self.label_etapa.setVisible(False)
        self.btn_cancelar.setEnabled(False)
        self.progress.setIndeterminate(False)
        self.smooth_progress_timer.stop()
        self.adicionar_ao_historico()
        self.adicionar_log_console("Transcrição finalizada com sucesso.")

    def exibir_erro(self, mensagem):
        self.texto_transcricao.setHtml(
            f'<div style="color:#ff7676;font-size:16px;"><b>Erro durante a transcrição:</b><br>{mensagem}</div>'
        )
        self.progress.setVisible(False)
        self.label_progresso.setVisible(False)
        self.label_etapa.setVisible(False)
        self.btn_cancelar.setEnabled(False)
        self.progress.setIndeterminate(False)
        self.smooth_progress_timer.stop()
        self.adicionar_log_console(f"Erro durante a transcrição: {mensagem}")

    def adicionar_ao_historico(self):
        """Adiciona transcrição atual ao histórico e salva no arquivo"""
        try:
            # Verificar se tem caminho de arquivo
            if not self.caminho_arquivo:
                return
                
            # Nome base do arquivo
            base = os.path.splitext(os.path.basename(self.caminho_arquivo))[0]
            nome_transcricao = f"transcricao_{base}.txt"
            
            # Caminho completo da transcrição
            caminho_transcricao = os.path.join(TRANSCRICOES_DIR, nome_transcricao)
            
            # Garantir que a pasta existe
            if not os.path.exists(TRANSCRICOES_DIR):
                os.makedirs(TRANSCRICOES_DIR, exist_ok=True)
                self.adicionar_log_console(f"Pasta de transcrições criada: {TRANSCRICOES_DIR}")
            
            # Salvar conteúdo atual da transcrição
            texto = self.texto_transcricao.toPlainText()
            if texto.strip():
                with open(caminho_transcricao, "w", encoding="utf-8") as f:
                    f.write(texto)
                self.adicionar_log_console(f"Transcrição salva em: {caminho_transcricao}")
            
            # Verificar tradução
            nome_traducao = f"transcricao_{base}_ingles.txt"
            caminho_traducao = os.path.join(TRANSCRICOES_DIR, nome_traducao)
            tem_traducao = os.path.exists(caminho_traducao)
            
            # Habilitar botão de baixar tradução se existir
            self.btn_download_traducao.setEnabled(tem_traducao)
            
            # Registrar no histórico
            idioma_cod = self.combo_idioma.currentData()
            data = {
                "arquivo": nome_transcricao,
                "nome": os.path.basename(self.caminho_arquivo),
                "caminho_completo": caminho_transcricao,
                "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "idioma": idioma_cod,
                "tem_traducao": tem_traducao
            }
            
            historico = self._ler_historico_arquivo()
            # Remover entrada anterior para o mesmo arquivo, se existir
            historico = [h for h in historico if h.get("arquivo") != data["arquivo"]]
            # Adicionar nova entrada no início
            historico.insert(0, data)
            max_itens = self.config.get("max_historico", 20)
            historico = historico[:max_itens]
            self._salvar_historico_arquivo(historico)
            self.carregar_historico()
            self.adicionar_log_console(f"Transcrição adicionada ao histórico: {nome_transcricao}")
        except Exception as e:
            self.adicionar_log_console(f"Erro ao adicionar ao histórico: {str(e)}")
            import traceback
            self.adicionar_log_console(traceback.format_exc())

    def carregar_historico(self):
        historico = self._ler_historico_arquivo()
        self._historico_cache = historico
        self.filtrar_historico(self.busca_historico.text())

    def _ler_historico_arquivo(self):
        if os.path.exists(HISTORICO_PATH):
            try:
                with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _salvar_historico_arquivo(self, historico):
        try:
            with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
                json.dump(historico, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar histórico: {str(e)}")

    def filtrar_historico(self, texto):
        texto = texto.strip().lower()
        self.lista_historico.clear()
        for h in self._historico_cache:
            nome = h['nome'].lower()
            data_str = h['data'].lower()
            idioma_str = h.get('idioma', 'auto')
            idioma_nome = next((n for c, n in IDIOMAS if c == idioma_str), idioma_str)
            if texto in nome or texto in data_str or texto in idioma_nome.lower():
                display = f"{h['nome']}  ({h['data']}, {idioma_nome})"
                self.lista_historico.addItem(display)

    def abrir_do_historico(self, item):
        """Corrigido para evitar 'nome_arquivo' undefined"""
        idx = self.lista_historico.currentRow()
        if idx < 0 or idx >= len(self._historico_cache):
            return
        
        try:
            # Obter dados do histórico
            entrada_historico = self._historico_cache[idx]
            
            # Verificar se temos informações necessárias
            if "arquivo" not in entrada_historico:
                QMessageBox.warning(self, "Aviso", "Registro de histórico inválido")
                return
                
            arquivo_nome = entrada_historico["arquivo"]
            
            # Verificar se temos caminho_completo no registro histórico
            if "caminho_completo" in entrada_historico and os.path.exists(entrada_historico["caminho_completo"]):
                caminho = entrada_historico["caminho_completo"]
            else:
                # Caminho tradicional baseado apenas no nome do arquivo
                caminho = os.path.join(TRANSCRICOES_DIR, arquivo_nome)
            
            # Verificar se existe
            if not os.path.exists(caminho):
                QMessageBox.warning(self, "Aviso", f"Arquivo de transcrição não encontrado: {caminho}")
                return
            
            # Ler o conteúdo
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read()
            
            # Exibir no editor
            self.texto_transcricao.setPlainText(conteudo)
            
            # Verificar se também existe tradução em inglês
            nome_base = os.path.splitext(arquivo_nome)[0]
            if nome_base.endswith("_ingles"):
                self.btn_download_traducao.setEnabled(False)
            else:
                # Verificar se existe versão em inglês
                caminho_traducao = os.path.join(TRANSCRICOES_DIR, f"{nome_base}_ingles.txt")
                self.btn_download_traducao.setEnabled(os.path.exists(caminho_traducao))
            
            self.adicionar_log_console(f"Transcrição do histórico carregada: {arquivo_nome}")
            
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao ler arquivo: {str(e)}")
            self.adicionar_log_console(f"Erro ao carregar transcrição do histórico: {str(e)}")

    def remover_selecionado(self):
        idx = self.lista_historico.currentRow()
        if idx < 0 or idx >= len(self._historico_cache):
            return
        to_remove = self._historico_cache[idx]
        historico = self._ler_historico_arquivo()
        historico = [h for h in historico if h["arquivo"] != to_remove["arquivo"]]
        self._salvar_historico_arquivo(historico)
        self.carregar_historico()
        self.adicionar_log_console(f"Entrada removida do histórico: {to_remove['nome']}")

    def limpar_historico(self):
        resp = QMessageBox.question(self, "Limpar histórico", "Tem certeza que deseja apagar todo o histórico?")
        if resp == QMessageBox.StandardButton.Yes:
            try:
                with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
                    json.dump([], f)
                self.adicionar_log_console("Histórico de transcrições limpo.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao apagar histórico: {str(e)}")
            self.carregar_historico()

    def baixar_transcricao(self):
        texto = self.texto_transcricao.toPlainText()
        if not texto.strip():
            QMessageBox.warning(self, "Aviso", "Nenhuma transcrição para baixar.")
            return
        
        base = os.path.splitext(os.path.basename(self.caminho_arquivo))[0] if self.caminho_arquivo else "transcricao"
        nome_sugestao = f"transcricao_{base}.txt"
        self._salvar_com_dialogo(texto, nome_sugestao)

    def baixar_traducao(self):
        """Baixa a tradução em inglês do arquivo selecionado"""
        try:
            # Verificar se temos um arquivo atual
            nome_base = None
            
            if self.caminho_arquivo:
                # Usar arquivo selecionado atualmente
                nome_base = os.path.splitext(os.path.basename(self.caminho_arquivo))[0]
            else:
                # Se não tiver arquivo selecionado, verificar histórico atual
                idx = self.lista_historico.currentRow()
                if idx >= 0 and idx < len(self._historico_cache):
                    entrada = self._historico_cache[idx]
                    nome_arquivo = entrada.get("arquivo", "")
                    if nome_arquivo:
                        # Remover possíveis prefixos/sufixos para obter o nome base
                        nome_base = nome_arquivo.replace("transcricao_", "")
                        nome_base = os.path.splitext(nome_base)[0]
                        
            if not nome_base:
                QMessageBox.warning(self, "Aviso", "Selecione um arquivo do histórico ou abra um arquivo para transcrição.")
                return
                
            # Tente encontrar o arquivo de tradução em vários formatos possíveis
            possiveis_caminhos = [
                os.path.join(TRANSCRICOES_DIR, f"transcricao_{nome_base}_ingles.txt"),
                os.path.join(TRANSCRICOES_DIR, f"{nome_base}_ingles.txt"),
                os.path.join(TRANSCRICOES_DIR, f"transcricao_{nome_base}_en.txt")
            ]
            
            # Verificar qual caminho existe
            caminho_trad = None
            for path in possiveis_caminhos:
                if os.path.exists(path):
                    caminho_trad = path
                    break
                    
            if not caminho_trad:
                QMessageBox.warning(self, "Aviso", 
                    "Arquivo de tradução não encontrado.\n\n"
                    "Certifique-se de que:\n"
                    "1. A transcrição foi realizada com um idioma específico (não 'Auto')\n"
                    "2. O processo de transcrição foi finalizado corretamente")
                self.adicionar_log_console(f"Arquivos de tradução não encontrados. Caminhos verificados: {possiveis_caminhos}")
                return
            
            # Ler o arquivo de tradução
            with open(caminho_trad, "r", encoding="utf-8") as f:
                texto = f.read()
            
            # Abrir diálogo para salvar
            nome_arquivo_sugerido = os.path.basename(caminho_trad)
            caminho_salvar, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar tradução como...",
                nome_arquivo_sugerido,
                "Arquivos de texto (*.txt);;Todos os arquivos (*)"
            )
            
            if caminho_salvar:
                with open(caminho_salvar, "w", encoding="utf-8") as f:
                    f.write(texto)
                self.adicionar_log_console(f"Tradução salva como: {caminho_salvar}")
                QMessageBox.information(self, "Sucesso", f"Tradução salva com sucesso em:\n{caminho_salvar}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao processar tradução: {str(e)}")
            self.adicionar_log_console(f"Erro ao baixar tradução: {str(e)}")
            import traceback
            self.adicionar_log_console(traceback.format_exc())

    def _salvar_com_dialogo(self, texto, sugestao_nome):
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar como...",
            sugestao_nome,
            "Text Files (*.txt);;All Files (*)"
        )
        if caminho:
            try:
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(texto)
                self.adicionar_log_console(f"Arquivo salvo: {caminho}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar arquivo: {str(e)}")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    janela = TranscricaoTab()
    janela.show()
    sys.exit(app.exec())