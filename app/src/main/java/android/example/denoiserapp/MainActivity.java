package android.example.denoiserapp;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.RequiresApi;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.Manifest;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.Toast;

import com.google.android.gms.tasks.OnSuccessListener;
import com.google.firebase.FirebaseApp;
import com.google.firebase.storage.FileDownloadTask;
import com.google.firebase.storage.FirebaseStorage;
import com.google.firebase.storage.StorageReference;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.ProtocolException;
import java.net.URL;
import java.nio.file.Files;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class MainActivity extends AppCompatActivity {
    Uri original_audio_uri = null;
    File DenoisedFile;
    File FinalFile;
    Button gmail_sender;
    ProgressBar progressBar;
    MediaPlayer mediaPlayer;
    int STORAGE_PERMISSION_CODE = 1;
    File copyFile;
    FirebaseStorage storage = FirebaseStorage.getInstance();
    String send_url = "https://denoiser-server.sites.tjhsst.edu/fileUpload";
    String out_url = "https://denoiser-server.sites.tjhsst.edu/download";
    @Override
    protected void onCreate(Bundle savedInstanceState) {


        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        ActivityCompat.requestPermissions( this,
                new String[]{
                        Manifest.permission.READ_EXTERNAL_STORAGE,
                        Manifest.permission.WRITE_EXTERNAL_STORAGE,
                        Manifest.permission.MANAGE_EXTERNAL_STORAGE
                }, 1
        );
        progressBar = (ProgressBar) findViewById(R.id.progressBar);
        gmail_sender = (Button) findViewById(R.id.gmail_sender);
        gmail_sender.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                Intent intent = new Intent(Intent.ACTION_SEND);
                intent.setType("vnd.android.cursor.dir/email");
                String[] emails = {"example@gmail.com"};
                intent.putExtra(Intent.EXTRA_EMAIL, emails);
                intent.putExtra(Intent.EXTRA_SUBJECT, "Subject");
                startActivity(Intent.createChooser(intent, "Send email..."));
            }
        });
    }
    public void denoise(View v) {
        if (original_audio_uri == null) {
            Toast.makeText(MainActivity.this, "Please select a file to denoise!", Toast.LENGTH_SHORT).show();
            return;
        }
        ExecutorService service = Executors.newSingleThreadExecutor();
        String filePath = original_audio_uri.getPath();
        String newPath = filePath.substring(filePath.indexOf(':')+1);
        File uploadFile = new File(newPath);
        String uploadFileName = uploadFile.getName();
        long start = System.nanoTime();
        service.execute(new Runnable() {
            @Override
            public void run() {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        progressBar.setVisibility(View.VISIBLE);
                    }
                });
                try  {
                    upload(send_url, uploadFile);
                    download(uploadFileName);
                } catch (Exception e) {
                    e.printStackTrace();
                }
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        long end = System.nanoTime();
                        System.out.println(end-start);
                        Toast.makeText(MainActivity.this, "Finished Denoising!", Toast.LENGTH_SHORT).show();
                        progressBar.setVisibility(View.INVISIBLE);
                    }
                });
            }
        });
    }
    public void download(String originalFileName) throws IOException {
        OkHttpClient client = new OkHttpClient();
        Request request = new Request.Builder().url(out_url).build();
        Response response = client.newCall(request).execute();
        InputStream inputStream = response.body().byteStream();
        String filename = originalFileName.substring(0, originalFileName.length()-4) + "_generated.wav";
        String downloadsFolder = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).getPath();
        File file = new File(downloadsFolder + File.separator + filename);
        FileOutputStream outputStream = new FileOutputStream(file);
        byte[] buffer = new byte[8192];
        int bytesRead = -1;
        while ((bytesRead = inputStream.read(buffer)) != -1)
            outputStream.write(buffer, 0, bytesRead);
        outputStream.close();
        inputStream.close();
    }
    private static void copyFile(String inputPath, String outputPath) {
        InputStream in = null;
        OutputStream out = null;
        try {
            //create output directory if it doesn't exist
            File dir = new File (outputPath);
            if (!dir.exists())
            {
                dir.mkdirs();
            }
            in = new FileInputStream(inputPath);
            System.out.println("here");
            out = new FileOutputStream(outputPath);

            byte[] buffer = new byte[1024];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            in.close();
            in = null;

            // write the output file (You have now copied the file)
            out.flush();
            out.close();
            out = null;

        }  catch (FileNotFoundException fnfe1) {
            Log.e("tag", fnfe1.getMessage());
        }
        catch (Exception e) {
            Log.e("tag", e.getMessage());
        }
    }
    public void select_file(View v) {
        if (ContextCompat.checkSelfPermission(MainActivity.this,
                Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestStoragePermission();
        }

        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.setType("audio/*");
        startActivityForResult(intent, 100);
    }
    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == 100) {
            original_audio_uri = data.getData();
        }
    }
    public void upload(String url, File file) throws IOException {
        OkHttpClient client = new OkHttpClient().newBuilder()
                .connectTimeout(300, TimeUnit.SECONDS)
                .writeTimeout(300, TimeUnit.SECONDS)
                .readTimeout(300, TimeUnit.SECONDS).build();
        RequestBody formBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("sample", file.getName(),
                        RequestBody.create(MediaType.parse("*/*"), file))
                .build();
        Request request = new Request.Builder().url(url).post(formBody).build();
        Response response = client.newCall(request).execute();
    }
    private void requestStoragePermission() {
        if (ActivityCompat.shouldShowRequestPermissionRationale(this, Manifest.permission.READ_EXTERNAL_STORAGE)) {
            new AlertDialog.Builder(this)
                .setTitle("Permission Needed")
                .setMessage("This permission is needed to access your files")
                .setPositiveButton("ok", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialogInterface, int i) {
                        ActivityCompat.requestPermissions(MainActivity.this, new String[] {Manifest.permission.READ_EXTERNAL_STORAGE}, STORAGE_PERMISSION_CODE);
                    }
                }).setNegativeButton("cancel", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialogInterface, int i) {
                        dialogInterface.dismiss();
                    }
                })
                .create()
                .show();
        } else {
            ActivityCompat.requestPermissions(this, new String[] {Manifest.permission.READ_EXTERNAL_STORAGE}, STORAGE_PERMISSION_CODE);
        }
    }
    public void play(View v) {
        try {
            mediaPlayer = MediaPlayer.create(getApplicationContext(), original_audio_uri);
            mediaPlayer.start();
        } catch (Exception e) {
            Toast.makeText(this, "You have not selected an audio file!", Toast.LENGTH_SHORT).show();
        }
    }
    public void pause(View v) {
        if (mediaPlayer != null) {
            mediaPlayer.pause();
        }
    }
    public void stop(View v) {stopPlayer(); }

    private void stopPlayer() {
        if (mediaPlayer != null) {
            mediaPlayer.release();
            mediaPlayer = null;
            Toast.makeText(this, "MediaPlayer release", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onStop(){
        super.onStop();
        stopPlayer();
    }
}