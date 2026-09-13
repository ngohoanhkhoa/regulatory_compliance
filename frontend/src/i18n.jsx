import { createContext, useContext, useEffect, useState } from "react";
import { getSettings, setSetting } from "./api/settings";

// English strings are the keys; a missing translation falls back to English.
const TRANSLATIONS = {
  en: {},
  fr: {
    // Nav / shell
    Chat: "Discussion",
    Topics: "Thèmes",
    Datasets: "Jeux de données",
    Settings: "Paramètres",
    "Sign Out": "Déconnexion",
    "Account & settings": "Compte et paramètres",

    // Login
    "AI-powered answers about EU legal obligations, grounded in the CEPS EurLex dataset with full citations.":
      "Réponses assistées par IA sur les obligations juridiques de l'UE, fondées sur le jeu de données CEPS EurLex avec citations complètes.",
    "Sign In": "Connexion",
    Register: "S'inscrire",
    Username: "Nom d'utilisateur",
    Password: "Mot de passe",
    "Username ≥ 3 characters, password ≥ 8 characters.":
      "Nom d'utilisateur ≥ 3 caractères, mot de passe ≥ 8 caractères.",
    "Create Account": "Créer un compte",
    "Authentication failed": "Échec de l'authentification",

    // Settings
    "Settings saved": "Paramètres enregistrés",
    Account: "Compte",
    "Save username": "Enregistrer le nom",
    "Change password": "Changer le mot de passe",
    "Current password": "Mot de passe actuel",
    "New password": "Nouveau mot de passe",
    "Confirm new password": "Confirmer le nouveau mot de passe",
    "Username updated.": "Nom d'utilisateur mis à jour.",
    "New password must be at least 8 characters.":
      "Le nouveau mot de passe doit comporter au moins 8 caractères.",
    "New passwords do not match.": "Les nouveaux mots de passe ne correspondent pas.",
    "Password changed.": "Mot de passe modifié.",
    Retrieval: "Recherche",
    "Include repealed / superseded acts": "Inclure les actes abrogés / remplacés",
    "When enabled, search results include legislation that has been repealed, expired, or superseded. Disabled by default — only In Force acts are returned.":
      "Si activé, les résultats incluent les textes abrogés, expirés ou remplacés. Désactivé par défaut — seuls les actes en vigueur sont renvoyés.",
    Display: "Affichage",
    "Dark mode": "Mode sombre",
    "Use dark color scheme throughout the application.":
      "Utiliser un thème sombre dans toute l'application.",
    "Auto-expand sources": "Développer automatiquement les sources",
    "Automatically expand the sources panel in chat responses.":
      "Développer automatiquement le panneau des sources dans les réponses.",
    Language: "Langue",
    "Answer language": "Langue des réponses",
    "Interface & answers": "Interface et réponses",
    "Changes the interface language and the language the assistant replies in. CELEX numbers, act titles, and links stay unchanged.":
      "Change la langue de l'interface et celle des réponses de l'assistant. Les numéros CELEX, titres et liens restent inchangés.",
    "The language the assistant replies in. CELEX numbers, act titles, and links are kept unchanged.":
      "La langue dans laquelle l'assistant répond. Les numéros CELEX, titres et liens restent inchangés.",
    Notifications: "Notifications",
    "Enable notifications": "Activer les notifications",
    "Receive browser notifications for long-running queries.":
      "Recevoir des notifications du navigateur pour les requêtes longues.",
    "API Information": "Informations sur l'API",
    "Local vector store with CEPS EurLex dataset":
      "Base vectorielle locale avec le jeu de données CEPS EurLex",
    "LLM generation via OpenRouter API": "Génération LLM via l'API OpenRouter",
    "Dataset frozen at August 2019": "Jeu de données figé en août 2019",
    Users: "Utilisateurs",
    "New Topic": "Nouveau thème",
    "Filter topics…": "Filtrer les thèmes…",
    "No topics yet": "Aucun thème pour l'instant",
    "No topics match your filter": "Aucun thème ne correspond au filtre",
    "Edit Topic": "Modifier le thème",
    "Save changes": "Enregistrer les modifications",
    "Create topic": "Créer le thème",
    "Refreshing…": "Actualisation…",
    Refresh: "Actualiser",
    "Track a regulatory topic": "Suivre un thème réglementaire",
    "Create your first topic": "Créez votre premier thème",
    "Delete topic": "Supprimer le thème",
    "Add user": "Ajouter un utilisateur",
    Role: "Rôle",
    Created: "Créé",
    Actions: "Actions",
    you: "vous",
    admin: "admin",
    user: "utilisateur",

    // Chat
    Conversations: "Conversations",
    "New Chat": "Nouvelle discussion",
    "Recent History": "Historique récent",
    Open: "Ouvrir",
    "No recent chats yet": "Aucune discussion récente",
    "Ask about EU regulations": "Posez une question sur la réglementation de l'UE",
    "Ask legal questions like \"Is the GDPR still in force?\" or explore the dataset with \"How many acts are there?\"":
      "Posez des questions juridiques comme « Le RGPD est-il toujours en vigueur ? » ou explorez le corpus avec « Combien d'actes existe-t-il ? »",
    "Ask a question… type @ to mention a document or act":
      "Posez une question… tapez @ pour mentionner un document ou un acte",
    "Understanding your question…": "Analyse de votre question…",
    "Searching EU legislation…": "Recherche dans la législation de l'UE…",
    "Generating response…": "Génération de la réponse…",
    Copy: "Copier",
    Copied: "Copié",
    Sources: "sources",
    "Chat History": "Historique des discussions",
    "Query failed": "Échec de la requête",

    // Datasets
    "Your private documents and the regulatory text collections you can chat with. Regulatory datasets are shared read-only; admins can import or remove them.":
      "Vos documents privés et les collections de textes réglementaires avec lesquelles discuter. Les jeux réglementaires sont partagés en lecture seule ; les admins peuvent les importer ou les supprimer.",
    "Import regulatory dataset": "Importer un jeu réglementaire",
    "Regulatory texts": "Textes réglementaires",
    "My documents": "Mes documents",
    "No regulatory datasets yet.": "Aucun jeu réglementaire pour l'instant.",
    "Loading datasets…": "Chargement des jeux de données…",
    items: "éléments",
    chunks: "fragments",
    vectors: "vecteurs",
    Regulatory: "Réglementaire",
    Documents: "Documents",
    "All datasets": "Tous les jeux",
    "Export bundle": "Exporter le paquet",
    "Remove dataset": "Supprimer le jeu",
    Items: "Éléments",
    "Text chunks": "Fragments de texte",
    "Indexed vectors": "Vecteurs indexés",
    Source: "Source",
    "Search by ID, title, or status…": "Rechercher par ID, titre ou statut…",
    Search: "Rechercher",
    "No items found.": "Aucun élément trouvé.",
    "Loading items…": "Chargement des éléments…",
    "Loading item…": "Chargement de l'élément…",
    "Loading dataset…": "Chargement du jeu de données…",
    "Showing {from}–{to} of {total}": "Affichage {from}–{to} sur {total}",
    First: "Premier",
    Prev: "Préc.",
    Next: "Suiv.",
    Last: "Dernier",
    "Page {page} / {pages}": "Page {page} / {pages}",
    "{n} / page": "{n} / page",
    "Export dataset bundle": "Exporter le paquet du jeu",
    Export: "Exporter",
    Cancel: "Annuler",
    "Include precomputed embeddings (larger file)":
      "Inclure les embeddings précalculés (fichier plus volumineux)",

    // Documents
    "My Documents": "Mes documents",
    "Add your own files (PDF, DOCX, TXT, MD, CSV). They are stored in your private library and indexed for semantic search — separate from the regulatory corpus.":
      "Ajoutez vos propres fichiers (PDF, DOCX, TXT, MD, CSV). Ils sont stockés dans votre bibliothèque privée et indexés pour la recherche sémantique — séparément du corpus réglementaire.",
    "Tags / collection (optional) — e.g. contracts, 2024":
      "Étiquettes / collection (facultatif) — ex. contrats, 2024",
    "Choose files or drop them here — PDF, DOCX, TXT, MD, CSV":
      "Choisissez des fichiers ou déposez-les ici — PDF, DOCX, TXT, MD, CSV",
    "Uploading and indexing…": "Téléversement et indexation…",
    "My Documents ({n})": "Mes documents ({n})",
    "No documents yet. Add your first file above.":
      "Aucun document pour l'instant. Ajoutez votre premier fichier ci-dessus.",
    "Search my documents": "Rechercher dans mes documents",
    "Ask something about your documents…":
      "Posez une question sur vos documents…",
    Searching: "Recherche",
    "Searching…": "Recherche…",
    "No matches in your documents.": "Aucune correspondance dans vos documents.",
    "Choose files or drop them here — PDF, DOCX, TXT, MD, CSV":
      "Choisissez des fichiers ou déposez-les ici — PDF, DOCX, TXT, MD, CSV",
    Library: "Bibliothèque",
    Uploaded: "Téléversé",
    "Delete this document and its indexed chunks?":
      "Supprimer ce document et ses fragments indexés ?",

    // Users panel
    "Users ({n})": "Utilisateurs ({n})",
    "Delete user": "Supprimer l'utilisateur",
    "Reset password": "Réinitialiser le mot de passe",
    "Rename user": "Renommer l'utilisateur",
    "Remove admin": "Retirer l'admin",
    "Make admin": "Nommer admin",
    "Change username": "Changer le nom d'utilisateur",
    "New username": "Nouveau nom d'utilisateur",
    "Loading users…": "Chargement des utilisateurs…",
    Save: "Enregistrer",
    "Create user": "Créer l'utilisateur",
    "Grant admin rights": "Accorder les droits d'admin",
  },
  vi: {
    // Nav / shell
    Chat: "Trò chuyện",
    Topics: "Chủ đề",
    Datasets: "Bộ dữ liệu",
    Settings: "Cài đặt",
    "Sign Out": "Đăng xuất",
    "Account & settings": "Tài khoản & cài đặt",

    // Login
    "AI-powered answers about EU legal obligations, grounded in the CEPS EurLex dataset with full citations.":
      "Câu trả lời bằng AI về các nghĩa vụ pháp lý EU, dựa trên bộ dữ liệu CEPS EurLex kèm trích dẫn đầy đủ.",
    "Sign In": "Đăng nhập",
    Register: "Đăng ký",
    Username: "Tên đăng nhập",
    Password: "Mật khẩu",
    "Username ≥ 3 characters, password ≥ 8 characters.":
      "Tên đăng nhập ≥ 3 ký tự, mật khẩu ≥ 8 ký tự.",
    "Create Account": "Tạo tài khoản",
    "Authentication failed": "Xác thực thất bại",

    // Settings
    "Settings saved": "Đã lưu cài đặt",
    Account: "Tài khoản",
    "Save username": "Lưu tên đăng nhập",
    "Change password": "Đổi mật khẩu",
    "Current password": "Mật khẩu hiện tại",
    "New password": "Mật khẩu mới",
    "Confirm new password": "Xác nhận mật khẩu mới",
    "Username updated.": "Đã cập nhật tên đăng nhập.",
    "New password must be at least 8 characters.":
      "Mật khẩu mới phải có ít nhất 8 ký tự.",
    "New passwords do not match.": "Mật khẩu mới không khớp.",
    "Password changed.": "Đã đổi mật khẩu.",
    Retrieval: "Truy xuất",
    "Include repealed / superseded acts": "Bao gồm văn bản đã bãi bỏ / thay thế",
    "When enabled, search results include legislation that has been repealed, expired, or superseded. Disabled by default — only In Force acts are returned.":
      "Khi bật, kết quả tìm kiếm bao gồm văn bản đã bãi bỏ, hết hiệu lực hoặc bị thay thế. Mặc định tắt — chỉ trả về văn bản còn hiệu lực.",
    Display: "Hiển thị",
    "Dark mode": "Chế độ tối",
    "Use dark color scheme throughout the application.":
      "Dùng giao diện tối cho toàn bộ ứng dụng.",
    "Auto-expand sources": "Tự động mở rộng nguồn",
    "Automatically expand the sources panel in chat responses.":
      "Tự động mở rộng bảng nguồn trong câu trả lời.",
    Language: "Ngôn ngữ",
    "Answer language": "Ngôn ngữ trả lời",
    "Interface & answers": "Giao diện & câu trả lời",
    "Changes the interface language and the language the assistant replies in. CELEX numbers, act titles, and links stay unchanged.":
      "Thay đổi ngôn ngữ giao diện và ngôn ngữ trợ lý trả lời. Số CELEX, tiêu đề văn bản và liên kết được giữ nguyên.",
    "The language the assistant replies in. CELEX numbers, act titles, and links are kept unchanged.":
      "Ngôn ngữ trợ lý trả lời. Số CELEX, tiêu đề văn bản và liên kết được giữ nguyên.",
    Notifications: "Thông báo",
    "Enable notifications": "Bật thông báo",
    "Receive browser notifications for long-running queries.":
      "Nhận thông báo trình duyệt cho các truy vấn lâu.",
    "API Information": "Thông tin API",
    "Local vector store with CEPS EurLex dataset":
      "Kho vector cục bộ với bộ dữ liệu CEPS EurLex",
    "LLM generation via OpenRouter API": "Sinh văn bản LLM qua API OpenRouter",
    "Dataset frozen at August 2019": "Bộ dữ liệu cố định tháng 8/2019",
    Users: "Người dùng",
    "New Topic": "Chủ đề mới",
    "Filter topics…": "Lọc chủ đề…",
    "No topics yet": "Chưa có chủ đề",
    "No topics match your filter": "Không có chủ đề khớp bộ lọc",
    "Edit Topic": "Sửa chủ đề",
    "Save changes": "Lưu thay đổi",
    "Create topic": "Tạo chủ đề",
    "Refreshing…": "Đang làm mới…",
    Refresh: "Làm mới",
    "Track a regulatory topic": "Theo dõi một chủ đề quy định",
    "Create your first topic": "Tạo chủ đề đầu tiên",
    "Delete topic": "Xóa chủ đề",
    "Add user": "Thêm người dùng",
    Role: "Vai trò",
    Created: "Ngày tạo",
    Actions: "Thao tác",
    you: "bạn",
    admin: "quản trị",
    user: "người dùng",

    // Chat
    Conversations: "Cuộc trò chuyện",
    "New Chat": "Trò chuyện mới",
    "Recent History": "Lịch sử gần đây",
    Open: "Mở",
    "No recent chats yet": "Chưa có cuộc trò chuyện nào",
    "Ask about EU regulations": "Hỏi về quy định của EU",
    "Ask legal questions like \"Is the GDPR still in force?\" or explore the dataset with \"How many acts are there?\"":
      "Đặt câu hỏi pháp lý như “GDPR còn hiệu lực không?” hoặc khám phá dữ liệu với “Có bao nhiêu văn bản?”",
    "Ask a question… type @ to mention a document or act":
      "Đặt câu hỏi… gõ @ để nhắc đến tài liệu hoặc văn bản",
    "Understanding your question…": "Đang phân tích câu hỏi…",
    "Searching EU legislation…": "Đang tìm trong pháp luật EU…",
    "Generating response…": "Đang tạo câu trả lời…",
    Copy: "Sao chép",
    Copied: "Đã sao chép",
    Sources: "nguồn",
    "Chat History": "Lịch sử trò chuyện",
    "Query failed": "Truy vấn thất bại",

    // Datasets
    "Your private documents and the regulatory text collections you can chat with. Regulatory datasets are shared read-only; admins can import or remove them.":
      "Tài liệu riêng của bạn và các bộ văn bản quy định để trò chuyện. Bộ quy định được chia sẻ chỉ đọc; quản trị viên có thể nhập hoặc xóa.",
    "Import regulatory dataset": "Nhập bộ dữ liệu quy định",
    "Regulatory texts": "Văn bản quy định",
    "My documents": "Tài liệu của tôi",
    "No regulatory datasets yet.": "Chưa có bộ quy định nào.",
    "Loading datasets…": "Đang tải bộ dữ liệu…",
    items: "mục",
    chunks: "đoạn",
    vectors: "vector",
    Regulatory: "Quy định",
    Documents: "Tài liệu",
    "All datasets": "Tất cả bộ dữ liệu",
    "Export bundle": "Xuất gói",
    "Remove dataset": "Xóa bộ dữ liệu",
    Items: "Mục",
    "Text chunks": "Đoạn văn bản",
    "Indexed vectors": "Vector đã lập chỉ mục",
    Source: "Nguồn",
    "Search by ID, title, or status…": "Tìm theo ID, tiêu đề hoặc trạng thái…",
    Search: "Tìm kiếm",
    "No items found.": "Không tìm thấy mục nào.",
    "Loading items…": "Đang tải các mục…",
    "Loading item…": "Đang tải mục…",
    "Loading dataset…": "Đang tải bộ dữ liệu…",
    "Showing {from}–{to} of {total}": "Hiển thị {from}–{to} trong {total}",
    First: "Đầu",
    Prev: "Trước",
    Next: "Sau",
    Last: "Cuối",
    "Page {page} / {pages}": "Trang {page} / {pages}",
    "{n} / page": "{n} / trang",
    "Export dataset bundle": "Xuất gói bộ dữ liệu",
    Export: "Xuất",
    Cancel: "Hủy",
    "Include precomputed embeddings (larger file)":
      "Bao gồm embeddings tính sẵn (tệp lớn hơn)",

    // Documents
    "My Documents": "Tài liệu của tôi",
    "Add your own files (PDF, DOCX, TXT, MD, CSV). They are stored in your private library and indexed for semantic search — separate from the regulatory corpus.":
      "Thêm tệp của bạn (PDF, DOCX, TXT, MD, CSV). Chúng được lưu trong thư viện riêng và lập chỉ mục để tìm kiếm ngữ nghĩa — tách biệt với kho quy định.",
    "Tags / collection (optional) — e.g. contracts, 2024":
      "Thẻ / bộ sưu tập (tùy chọn) — ví dụ: hợp đồng, 2024",
    "Choose files or drop them here — PDF, DOCX, TXT, MD, CSV":
      "Chọn tệp hoặc kéo thả vào đây — PDF, DOCX, TXT, MD, CSV",
    "Uploading and indexing…": "Đang tải lên và lập chỉ mục…",
    "My Documents ({n})": "Tài liệu của tôi ({n})",
    "No documents yet. Add your first file above.":
      "Chưa có tài liệu nào. Thêm tệp đầu tiên ở trên.",
    "Search my documents": "Tìm trong tài liệu của tôi",
    "Ask something about your documents…":
      "Hỏi điều gì đó về tài liệu của bạn…",
    Searching: "Đang tìm",
    "Searching…": "Đang tìm…",
    "No matches in your documents.": "Không có kết quả trong tài liệu của bạn.",
    "Choose files or drop them here — PDF, DOCX, TXT, MD, CSV":
      "Chọn tệp hoặc kéo thả vào đây — PDF, DOCX, TXT, MD, CSV",
    Library: "Thư viện",
    Uploaded: "Đã tải lên",
    "Delete this document and its indexed chunks?":
      "Xóa tài liệu này và các đoạn đã lập chỉ mục?",

    // Users panel
    "Users ({n})": "Người dùng ({n})",
    "Delete user": "Xóa người dùng",
    "Reset password": "Đặt lại mật khẩu",
    "Rename user": "Đổi tên người dùng",
    "Remove admin": "Bỏ quyền admin",
    "Make admin": "Cấp quyền admin",
    "Change username": "Đổi tên đăng nhập",
    "New username": "Tên đăng nhập mới",
    "Loading users…": "Đang tải người dùng…",
    Save: "Lưu",
    "Create user": "Tạo người dùng",
    "Grant admin rights": "Cấp quyền quản trị",
  },
};

const I18nContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => getSettings().language || "en");

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (code) => {
    setLangState(code);
    setSetting("language", code);
  };

  const t = (key, vars) => {
    let value = TRANSLATIONS[lang]?.[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        value = value.replaceAll(`{${k}}`, String(v));
      }
    }
    return value;
  };

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return { lang: "en", setLang: () => {}, t: (key) => key };
  }
  return ctx;
}
