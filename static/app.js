// Datei: static/app.js
// Stellen Sie sicher, dass alle Formulare HTTPS verwenden
document.addEventListener('DOMContentLoaded', function() {
    console.log("App.js geladen - Formular-Sicherheitsüberprüfung aktiv");

    // Alle Formulare auf der Seite finden
    var forms = document.querySelectorAll('form');

    forms.forEach(function(form) {
        // Aktuelle URL des Formulars speichern
        var currentAction = form.getAttribute('action');

        // Wenn das Formular eine action hat und diese mit http:// beginnt
        if (currentAction && currentAction.toLowerCase().startsWith('http://')) {
            // Ändere das Protokoll zu HTTPS
            form.action = currentAction.replace('http://', 'https://');
            console.log('Formular-Action zu HTTPS geändert:', form.action);
        }
    });

    // Alle Links auf der Seite finden
    var links = document.querySelectorAll('a[href]');

    // Für jeden Link
    links.forEach(function(link) {
        // Wenn der Link mit http:// beginnt und wir auf einer HTTPS-Seite sind
        if (link.href.toLowerCase().startsWith('http://') &&
            window.location.protocol === 'https:') {
            // Ändere das Protokoll zu HTTPS
            link.href = link.href.replace('http://', 'https://');
            console.log('Link-href zu HTTPS geändert:', link.href);
        }
    });
});