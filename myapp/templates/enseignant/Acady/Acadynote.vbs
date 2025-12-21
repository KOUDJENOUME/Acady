' start_acady_with_ngrok_file.vbs
Option Explicit

Dim objShell, fso
Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' === CONFIGURATION ===
Dim port : port = "8003"
Dim acadyPath : acadyPath = "C:\Acady"
Dim ngrokPath : ngrokPath = "C:\Acady\ngrok.exe"
Dim linkFolder : linkFolder = acadyPath & "\lien"

' Crée le dossier pour le lien si nécessaire
If Not fso.FolderExists(linkFolder) Then
    fso.CreateFolder(linkFolder)
End If

' ---------- FONCTIONS ----------

' Vérifie si un port est vraiment utilisé
Function IsPortReallyInUse(port)
    Dim cmd, exec, output
    cmd = "cmd /c netstat -ano | findstr :" & port
    Set exec = objShell.Exec(cmd)
    output = exec.StdOut.ReadAll
    IsPortReallyInUse = (Trim(output) <> "")
End Function

' Tue les processus Django restants
Sub KillOldDjango()
    Dim colProcesses, objProcess
    Set colProcesses = GetObject("winmgmts:\\.\root\cimv2").ExecQuery("SELECT * FROM Win32_Process WHERE Name='python.exe'")
    For Each objProcess In colProcesses
        If InStr(objProcess.CommandLine, "manage.py runserver") > 0 Then
            objProcess.Terminate
        End If
    Next
End Sub

' Démarre le serveur Django
Sub StartDjango()
    KillOldDjango() ' Nettoie les anciens processus
    WScript.Sleep 2000 ' Petit délai pour libérer le port

    If IsPortReallyInUse(port) Then
        MsgBox "Le port " & port & " est toujours occupé.", vbExclamation, "Serveur non démarré"
        WScript.Quit 1
    End If

    Dim cmd
    cmd = "cmd.exe /c cd /d """ & acadyPath & """ && python manage.py runserver 127.0.0.1:" & port & " >nul 2>&1"
    objShell.Run cmd, 0, False
End Sub

' Attendre que Django démarre (vérifie le port)
Function WaitForDjango(port, timeoutSeconds)
    Dim startTime
    startTime = Timer
    Do
        If IsPortReallyInUse(port) Then
            WaitForDjango = True
            Exit Function
        End If
        WScript.Sleep 1000
    Loop While Timer - startTime < timeoutSeconds
    WaitForDjango = False
End Function

' Lance ngrok si besoin
Sub StartNgrokIfNeeded()
    If Not IsProcessRunningByName("ngrok.exe") Then
        If Not fso.FileExists(ngrokPath) Then
            MsgBox "ngrok introuvable à : " & ngrokPath, vbCritical, "Erreur ngrok"
            WScript.Quit 1
        End If
        Dim cmd
        cmd = """" & ngrokPath & """" & " http " & port & " --log=stdout"
        objShell.Run cmd, 0, False
    End If
End Sub

' Vérifie si un processus existe
Function IsProcessRunningByName(procName)
    Dim WMIService, colItems
    Set WMIService = GetObject("winmgmts:\\.\root\cimv2")
    Set colItems = WMIService.ExecQuery("SELECT * FROM Win32_Process WHERE Name = '" & procName & "'")
    IsProcessRunningByName = (colItems.Count > 0)
End Function

' Attendre que ngrok expose le tunnel
Function WaitForNgrok(timeoutSeconds)
    Dim startTime, url
    startTime = Timer
    Do
        url = GetNgrokPublicURL()
        If url <> "" Then
            WaitForNgrok = url
            Exit Function
        End If
        WScript.Sleep 1000
    Loop While Timer - startTime < timeoutSeconds
    WaitForNgrok = ""
End Function

' Récupère le lien public ngrok
Function GetNgrokPublicURL()
    On Error Resume Next
    Dim http, body, re, matches
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.Open "GET", "http://127.0.0.1:4040/api/tunnels", False
    http.Send
    If Err.Number <> 0 Then
        GetNgrokPublicURL = ""
        Err.Clear
        Exit Function
    End If
    body = http.ResponseText
    On Error GoTo 0

    Set re = New RegExp
    re.Pattern = """public_url""\s*:\s*""(https?:\/\/[^""]+)"""
    re.Global = False
    re.IgnoreCase = True

    If re.Test(body) Then
        Set matches = re.Execute(body)
        GetNgrokPublicURL = matches(0).SubMatches(0)
    Else
        GetNgrokPublicURL = ""
    End If
End Function

' Enregistre le lien ngrok dans le dossier projet
Sub WriteNgrokURL(url)
    Dim filePath, ts
    filePath = linkFolder & "\lien_ngrok.txt"
    Set ts = fso.OpenTextFile(filePath, 2, True)
    ts.WriteLine url
    ts.Close

    MsgBox "✅ Lien ngrok enregistré dans : " & filePath, vbInformation, "Lien sauvegardé"
End Sub

' ---------- MAIN ----------
StartDjango()

If Not WaitForDjango(port, 20) Then
    MsgBox "Le serveur Django n'a pas démarré à temps.", vbCritical, "Erreur"
    WScript.Quit 1
End If

StartNgrokIfNeeded()

Dim ngrokUrl
ngrokUrl = WaitForNgrok(15)
If ngrokUrl = "" Then
    MsgBox "Impossible de récupérer l'URL ngrok. Vérifie que ngrok tourne bien.", vbCritical, "Erreur ngrok"
    WScript.Quit 1
End If

WriteNgrokURL ngrokUrl

' Ouvre le navigateur vers Django
objShell.Run "http://127.0.0.1:" & port, 1, False

' Nettoyage
Set objShell = Nothing
Set fso = Nothing
